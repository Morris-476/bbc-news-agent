import logging
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MINIMAL_CSS = """
body::before {
    content: attr(data-source-url);
    font-family: Arial, sans-serif;
    font-size: 10px;
    color: #888;
    display: block;
    padding: 3px 0 8px;
    border-bottom: 1px solid #ddd;
    margin-bottom: 10px;
}
@page { size: A4; margin: 1.5cm 2cm; }
img { max-width: 100% !important; height: auto !important; }

/* Force full-width for all article content blocks */
@media print {
    article > div, article > div > div,
    [data-component] [class*="LayoutBlock"],
    [data-component] [class*="GridStyled"],
    [data-component] [class*="GridItem"] {
        max-width: 100% !important;
        width: 100% !important;
    }
}
"""

BLOCKED_DOMAINS = [
    "trc.taboola.com", "cdn.taboola.com", "lb.taboola.com",
    "doubleclick.net", "googlesyndication.com", "googletagmanager.com",
    "chartbeat.com", "scorecardresearch.com", "omtrdc.net",
    "adobedtm.com", "amazon-adsystem.com",
]

CLEANUP_JS = """
() => {
    // 1. Remove fixed/sticky (banners, nav, cookie popups)
    document.querySelectorAll('*').forEach(el => {
        try {
            const s = window.getComputedStyle(el);
            if (s.position === 'fixed' || s.position === 'sticky') el.remove();
        } catch(e) {}
    });

    // 2. Remove structural nav/header/footer
    document.querySelectorAll('header, footer, nav').forEach(el => el.remove());

    // 3. Remove video/media blocks
    document.querySelectorAll('[data-component="media-block"]').forEach(el => {
        let target = el;
        while (target.parentElement && !target.parentElement.hasAttribute('data-component')) {
            target = target.parentElement;
        }
        target.style.display = 'none';
    });

    // 4. Remove ads, Taboola, social share bars, related stories
    const selectors = [
        '[data-component="ad-slot"]',
        '[data-component="advertisement-block"]',
        '[data-component="tag-list-block"]',
        '[id*="taboola"]', '[class*="taboola"]',
        '[data-testid="share-tools"]',
        '[data-testid="inline-share-tools"]',
        '[data-testid="google_preferred"]',
        'button[aria-label*="Share"]',
        'button[aria-label*="Save"]',
        '[data-testid^="ohio-section-outer"]',
    ];
    document.querySelectorAll(selectors.join(',')).forEach(el => el.remove());

    // 5. Force full-width on layout/text blocks (BBC print CSS constrains these)
    document.querySelectorAll(
        '[data-component="layout-block"], [data-component="text-block"]'
    ).forEach(el => {
        el.style.setProperty('max-width', 'none', 'important');
        el.style.setProperty('width', '100%', 'important');
    });
    document.querySelectorAll(
        '[data-component="layout-block"] [class*="Grid"],' +
        '[data-component="layout-block"] [class*="GridItem"],' +
        '[data-component="text-block"] [class*="Grid"],' +
        '[data-component="text-block"] [class*="GridItem"]'
    ).forEach(el => {
        el.style.setProperty('max-width', 'none', 'important');
        el.style.setProperty('width', '100%', 'important');
        el.style.setProperty('display', 'block', 'important');
    });
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
            viewport={"width": 1440, "height": 900},
            locale="en-US",
        )
        page = context.new_page()

        def route_handler(route):
            if any(d in route.request.url for d in BLOCKED_DOMAINS):
                route.abort()
            else:
                route.continue_()

        page.route("**/*", route_handler)
        page.goto(article["url"], wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)

        page.evaluate(CLEANUP_JS)

        url_escaped = article["url"].replace("'", "\\'")
        page.evaluate(f"document.body.setAttribute('data-source-url', '{url_escaped}');")
        page.add_style_tag(content=MINIMAL_CSS)
        page.wait_for_timeout(400)

        page.pdf(
            path=str(output_path),
            format="A4",
            print_background=True,
            margin={"top": "1.5cm", "bottom": "1.5cm", "left": "2cm", "right": "2cm"},
        )

        browser.close()

    logger.info(f"PDF 生成完成：{output_path}")
    return output_path
