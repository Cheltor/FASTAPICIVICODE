import os
import logging
from typing import Optional

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "no-reply@civicode.local")
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "true").lower() in ("1", "true", "yes", "on")
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL")  # e.g., https://app.example.com

logger = logging.getLogger(__name__)

def _should_send() -> bool:
    # Respect feature flag and ensure API key is present
    enabled = EMAIL_ENABLED
    has_key = bool(SENDGRID_API_KEY)
    if not enabled:
        logger.info("Email sending disabled by EMAIL_ENABLED feature flag")
    if not has_key:
        logger.warning("No SENDGRID_API_KEY configured; emails will not be sent")
    return enabled and has_key

def build_notification_html(subject: Optional[str], body: Optional[str], inspection_id: Optional[int] = None) -> str:
    safe_subject = subject or "Notification"
    safe_body = body or ""
    link_html = ""
    if FRONTEND_BASE_URL and inspection_id:
        link_html = f"<p><a href=\"{FRONTEND_BASE_URL}/inspection/{inspection_id}\">View inspection #{inspection_id}</a></p>"
    return f"""
        <div style=\"font-family: Arial, sans-serif; color: #111;\">
            <h2 style=\"margin:0 0 12px;\">{safe_subject}</h2>
            <div style=\"margin:0 0 16px;\">{safe_body}</div>
            {link_html}
            <hr style=\"margin:16px 0; border:none; border-top:1px solid #eee;\" />
            <p style=\"font-size:12px; color:#666;\">This is an automated message from CiviCode.</p>
        </div>
    """

def send_notification_email(subject: str, body: str, to_email: str, inspection_id: Optional[int] = None) -> bool:
    """
    Send a notification email via SendGrid.
    Returns True on success, False if skipped or failed.
    """
    try:
        if not _should_send():
            # Skip silently if disabled or no API key configured
            return False
        # Lazy import to avoid dependency issues if not installed
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        html_content = build_notification_html(subject, body, inspection_id)
        message = Mail(
            from_email=SENDGRID_FROM_EMAIL,
            to_emails=to_email,
            subject=subject or "Notification",
            html_content=html_content,
        )
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        return 200 <= getattr(response, "status_code", 500) < 300
    except Exception as exc:
        # Don't crash app due to email failure
        logger.exception("Failed to send notification email: %s", getattr(exc, 'message', str(exc)))
        return False
