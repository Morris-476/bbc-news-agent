import argparse
import logging
import sys
import traceback
from datetime import date, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scraper import get_article_for_session
from pdf_generator import generate_pdf
from email_sender import send_pdf_email, send_error_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

TW_TZ = timezone(timedelta(hours=8))
OUTPUT_DIR = Path(__file__).parent.parent / "output"


def main(session: str) -> None:
    today = date.today().strftime("%Y-%m-%d")
    logger.info(f"===== BBC News Agent 啟動 | {session} | {today} =====")

    last_error = None
    for attempt in range(1, 4):
        try:
            logger.info(f"第 {attempt} 次嘗試...")

            article = get_article_for_session(session)
            if article is None:
                raise RuntimeError("今日所有熱門文章均已使用，無法繼續")

            pdf_path = generate_pdf(article, OUTPUT_DIR, today)
            send_pdf_email(pdf_path, article, session, today)

            logger.info(f"===== 執行成功 ✅ =====")
            return

        except Exception as e:
            last_error = traceback.format_exc()
            logger.error(f"第 {attempt} 次失敗：{e}")
            if attempt < 3:
                import time
                logger.info("等待 30 秒後重試...")
                time.sleep(30)

    logger.error("三次嘗試均失敗，寄送錯誤通知...")
    try:
        send_error_email(last_error, session, today)
    except Exception as notify_err:
        logger.error(f"錯誤通知也失敗了：{notify_err}")
    sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BBC News Daily PDF Agent")
    parser.add_argument(
        "--session",
        choices=["noon", "evening"],
        required=True,
        help="執行時段：noon（12:00）或 evening（18:00）",
    )
    args = parser.parse_args()
    main(args.session)
