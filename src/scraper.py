import json
import os
import logging
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BBC_HOME = "https://www.bbc.com/news"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
USED_FILE = Path(__file__).parent.parent / "data" / "used_articles.json"


def _load_used() -> dict:
    if USED_FILE.exists():
        with open(USED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_used(data: dict) -> None:
    USED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _get_most_read() -> list[dict]:
    logger.info("正在抓取 BBC Most Read 列表...")
    resp = requests.get(BBC_HOME, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    articles = []

    most_read_section = soup.find("div", {"data-testid": "most-read"})
    if most_read_section:
        for a_tag in most_read_section.find_all("a", href=True):
            title = a_tag.get_text(strip=True)
            href = a_tag["href"]
            if title and "/news/articles/" in href:
                url = href if href.startswith("http") else f"https://www.bbc.com{href}"
                articles.append({"title": title, "url": url})

    if not articles:
        logger.warning("Most Read 區塊未找到，改抓首頁新聞連結...")
        seen_urls = set()
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if "/news/articles/" not in href:
                continue
            headline_el = a_tag.find(["h3", "h2", "h1"])
            title = headline_el.get_text(strip=True) if headline_el else a_tag.get_text(strip=True).split("  ")[0].strip()
            url = href if href.startswith("http") else f"https://www.bbc.com{href}"
            if len(title) > 10 and url not in seen_urls:
                seen_urls.add(url)
                articles.append({"title": title, "url": url})

    logger.info(f"找到 {len(articles)} 篇候選文章")
    return articles


def get_article_for_session(session: str) -> dict | None:
    today = str(date.today())
    used = _load_used()
    used_today = set(used.get(today, []))

    candidates = _get_most_read()

    for article in candidates:
        if article["url"] not in used_today:
            if today not in used:
                used[today] = []
            used[today].append(article["url"])

            cutoff = str(date.fromordinal(date.today().toordinal() - 7))
            used = {d: urls for d, urls in used.items() if d >= cutoff}

            _save_used(used)
            logger.info(f"[{session}] 選定文章：{article['title']}")
            return article

    logger.error("今日所有熱門文章均已使用過，無法選出新文章")
    return None
