import logging
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Minimal CSS: let BBC's own print CSS handle layout.
# We only remove things BBC's print CSS misses.
MINIMAL_CSS = """
/* Ads BBC print CSS doesn't hide */
[id*="taboola"], [class*="taboola"],
[data-component="advertisement-block"],
[class*="Backdrop"], [class*="Drawer"],
[data-testid="backdrop"], [data-testid="drawer-background"],
[data-testid="notification-banner"],
[class*="CookieBanner"], [class*="cookie-banner"],
[id*="sp_message"], [class*="sp_message"] {
    display: none !important;
}

/* Video/media hero: hide the player box */
[data-component="media-block"] {
    display: none !important;
}

/* Source URL watermark at top */
body::before {
    content: attr(data-source-url);
    font-family: Arial, sans-serif;
    font-size: 10px;
    color: #888;
    display: block;
    padding: 3px 0 6px;
    border-bottom: 1px solid #ddd;
    margin-bottom: 10px;
}

@page { size: A4; margin: 1.5cm 2cm; }
"""

# Domains to block at network level
BLOCKED_DOMAINS = [
    "trc.taboola.com", "cdn.taboola.com", "lb.taboola.com",
    "doubleclick.net", "googlesyndication.com", "googletagmanager.com",
    "chartbeat.com", "scorecardresearch.com", "omtrdc.net",
    "adobedtm.com", "adsystem.com", "amazon-adsystem.com",
]


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

        # Remove fixed/sticky elements (banners, cookie popups)
        page.evaluate("""
            document.querySelectorAll('*').forEach(el => {
                try {
                    const s = window.getComputedStyle(el);
                    if (s.position === 'fixed' || s.position === 'sticky') el.remove();
                } catch(e) {}
            });
        """)

        # Force full-width on text content blocks (BBC print CSS constrains these to ~40%)
        page.evaluate("""
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
        """)

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
