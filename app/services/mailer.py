import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger("app.mailer")


def _send(to_email: str, subject: str, html_body: str, text_body: str = ""):
    """Send an email via SMTP. Falls back to logging when disabled/empty creds."""
    if not settings.MAIL_ENABLED or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.info(
            "[MAIL DISABLED] To=%s Subject=%s\n%s",
            to_email,
            subject,
            html_body or text_body,
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["To"] = to_email
    msg["From"] = f"{settings.MAIL_FROM_NAME} <{settings.SMTP_USER}>"

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("Email sent to %s: %s", to_email, subject)
        return True
    except Exception as exc:  # pragma: no cover - network errors
        logger.error("Failed to send email to %s: %s", to_email, exc)
        return False


def _wrap(body: str) -> str:
    return f"""<div style="font-family:Arial,Helvetica,sans-serif;max-width:600px;margin:auto;border:1px solid #e0e0e0;border-radius:8px;overflow:hidden">
  <div style="background:#212529;color:#fff;padding:16px 24px;font-size:20px;font-weight:bold">{settings.MAIL_FROM_NAME}</div>
  <div style="padding:24px;color:#333">{body}</div>
  <div style="background:#f8f9fa;padding:12px 24px;font-size:12px;color:#888;text-align:center">{settings.MAIL_FROM_NAME} &middot; {settings.COMPANY_EMAIL}</div>
</div>"""


def notify_admin(subject: str, body: str):
    return _send(settings.ADMIN_EMAIL, subject, _wrap(body))


def notify_user(to_email: str, name: str, subject: str, body: str):
    return _send(to_email, subject, _wrap(body))
