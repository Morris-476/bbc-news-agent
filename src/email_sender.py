import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def send_pdf_email(
    pdf_path: Path,
    article: dict,
    session: str,
    date_str: str,
) -> None:
    gmail_user = os.environ["GMAIL_USER"]
    gmail_password = os.environ["GMAIL_APP_PASS"]
    recipient = os.environ["RECIPIENT_EMAIL"]

    session_label = "📰 中午版" if session == "noon" else "📰 晚間版"
    subject = f"[BBC News] {session_label} {date_str} — {article['title']}"

    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #bb1919; border-bottom: 2px solid #bb1919; padding-bottom: 8px;">
            BBC News Daily
        </h2>
        <p style="font-size: 14px; color: #555;">
            {session_label} &nbsp;|&nbsp; {date_str}
        </p>
        <h3 style="font-size: 20px; color: #111;">
            {article['title']}
        </h3>
        <p style="font-size: 13px;">
            <a href="{article['url']}" style="color: #bb1919;">原文連結</a>
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 16px 0;">
        <p style="font-size: 12px; color: #999;">
            PDF 附件已附上，請下載後於 Samsung Notes 開啟作筆記。
        </p>
    </div>
    """

    msg = MIMEMultipart("mixed")
    msg["From"] = gmail_user
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    with open(pdf_path, "rb") as f:
        pdf_data = f.read()
    attachment = MIMEApplication(pdf_data, _subtype="pdf")
    attachment.add_header(
        "Content-Disposition",
        "attachment",
        filename=pdf_path.name,
    )
    msg.attach(attachment)

    logger.info(f"正在寄送 email 到 {recipient}...")
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(gmail_user, gmail_password)
        smtp.sendmail(gmail_user, recipient, msg.as_string())

    logger.info(f"Email 寄送成功：{subject}")


def send_error_email(error_msg: str, session: str, date_str: str) -> None:
    gmail_user = os.environ["GMAIL_USER"]
    gmail_password = os.environ["GMAIL_APP_PASS"]
    recipient = os.environ["RECIPIENT_EMAIL"]

    session_label = "中午版" if session == "noon" else "晚間版"
    subject = f"[BBC Agent ⚠️] {date_str} {session_label} 執行失敗"

    body = f"""
    <div style="font-family: Arial, sans-serif;">
        <h3 style="color: #cc0000;">BBC News Agent 執行失敗通知</h3>
        <p><strong>時段：</strong>{session_label}</p>
        <p><strong>日期：</strong>{date_str}</p>
        <p><strong>錯誤訊息：</strong></p>
        <pre style="background: #f5f5f5; padding: 12px; border-radius: 4px;">
{error_msg}
        </pre>
        <hr>
        <p style="font-size: 12px; color: #999;">
            請前往 GitHub Actions 查看完整 log：
            https://github.com/Morris-476/bbc-news-agent/actions
        </p>
    </div>
    """

    msg = MIMEMultipart()
    msg["From"] = gmail_user
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(gmail_user, gmail_password)
            smtp.sendmail(gmail_user, recipient, msg.as_string())
        logger.info("錯誤通知 email 已寄出")
    except Exception as e:
        logger.error(f"連錯誤通知 email 也寄不出去：{e}")
