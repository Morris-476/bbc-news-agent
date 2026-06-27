import logging
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BBC_PRINT_CSS = """
header, footer, nav,
[data-testid="navigation"],
[data-testid="secondary-navigation"],
[data-testid="related-stories"],
[data-testid="advertisement"],
[data-testid="tout"],
[data-component="ad-slot"],
[class*="Ad-"],
[class*="ad-"],
[id*="ad-"],
[class*="promo"],
[class*="Promo"],
[data-testid="cookies-banner"],
[data-testid="user-notification"],
[class*="social-embed"],
[data-testid="topic-list"],
[data-testid="notification-banner"],
[class*="Banner"],
[class*="banner"],
[class*="Cookie"],
[class*="cookie"],
[id*="cookie"],
[id*="Cookie"],
.bbccom_slot,
.bbccom_display_none,
script, style, noscript,
[data-testid="timestamp"],
[data-testid="byline-new-contributors"],
aside {
    display: none !important;
}

body {
    font-family: "BBC Reith Serif", Georgia, "Times New Roman", serif !important;
    font-size: 18px !important;
    line-height: 1.6 !important;
    color: #222 !important;
    background: #fff !important;
    margin: 0 !important;
    padding: 0 !important;
}

[data-component="text-block"],
[data-testid="article-figure"],
article,
main {
    max-width: 100% !important;
    width: 100% !important;
    margin: 0 !important;
    padding: 0 12px !important;
    box-sizing: border-box !important;
}

h1 {
    font-family: "BBC Reith Serif", Georgia, serif !important;
    font-size: 28px !important;
    font-weight: 700 !important;
    line-height: 1.2 !important;
    color: #111 !important;
    margin: 20px 0 8px !important;
}

[data-testid="hero-headline-and-description"] p,
[data-component="description"] {
    font-size: 19px !important;
    font-weight: 400 !important;
    color: #444 !important;
    margin: 0 0 14px !important;
}

[data-testid="byline-new-contributors"],
time {
    font-family: "BBC Reith Sans", Arial, sans-serif !important;
    font-size: 13px !important;
    color: #555 !important;
    display: block !important;
    margin: 4px 0 18px !important;
}

body::before {
    content: attr(data-source-url);
    display: block;
    font-family: Arial, sans-serif;
    font-size: 11px;
    color: #666;
    padding: 6px 12px;
    border-bottom: 1px solid #ddd;
    margin-bottom: 12px;
}

p {
    font-size: 18px !important;
    line-height: 1.7 !important;
    margin: 0 0 18px !important;
    color: #222 !important;
}

img {
    max-width: 100% !important;
    height: auto !important;
    display: block !important;
    margin: 14px auto !important;
}

figcaption,
[data-testid="image-caption"] {
    font-size: 13px !important;
    color: #555 !important;
    text-align: center !important;
    margin: 4px 0 18px !important;
    font-style: italic !important;
}

blockquote {
    border-left: 4px solid #bb1919 !important;
    margin: 18px 0 !important;
    padding: 8px 16px !important;
    font-style: italic !important;
    color: #333 !important;
}

hr {
    border: none !important;
    border-top: 1px solid #ddd !important;
    margin: 20px 0 !important;
}

@page {
    margin: 1.5cm 2cm;
    size: A4;
}
"""


def _sanitize_filename(title: str, date_str: str) -> str:
    clean = re.sub(r"[^\w\s-]", "", title)
    clean = re.sub(r"\s+", "-", clean.strip())
    clean = clean[:60].rstrip("-")
    return f"{date_str}_{clean}.pdf"


def generate_pdf(article: dict, output_dir: Path, date_str: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = _sanitize_filename(article["title"], date_str)
    output_path = output_dir / filename

    logger.info(f"開始生成 PDF：{filename}")
    logger.info(f"文章 URL：{article['url']}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = context.new_page()

        # Block only trackers/ads; allow all images (BBC images have no extension in URL)
        def route_handler(route):
            url = route.request.url
            if any(x in url for x in ["doubleclick.net", "googlesyndication", "chartbeat", "scorecardresearch", "/ads/", "/analytics/"]):
                route.abort()
            else:
                route.continue_()

        page.route("**/*", route_handler)

        page.goto(article["url"], wait_until="networkidle", timeout=45000)

        # Remove fixed/sticky elements (cookie banners, notification bars)
        page.evaluate("""
            document.querySelectorAll('*').forEach(el => {
                const s = window.getComputedStyle(el);
                if (s.position === 'fixed' || s.position === 'sticky') {
                    el.remove();
                }
            });
        """)

        page.evaluate(f"document.body.setAttribute('data-source-url', '{article['url']}');")
        page.add_style_tag(content=BBC_PRINT_CSS)
        page.wait_for_timeout(800)

        page.pdf(
            path=str(output_path),
            format="A4",
            print_background=True,
            margin={
                "top": "1.5cm",
                "bottom": "1.5cm",
                "left": "2cm",
                "right": "2cm",
            },
        )

        browser.close()

    logger.info(f"PDF 生成完成：{output_path}")
    return output_path
