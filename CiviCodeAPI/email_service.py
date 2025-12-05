import os
import logging
from typing import Optional, List, Any
from datetime import datetime

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "no-reply@civicode.local")
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "true").lower() in ("1", "true", "yes", "on")
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")  # e.g., https://app.example.com

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


def build_password_reset_html(reset_url: Optional[str]) -> str:
    link_html = ""
    if reset_url:
        link_html = f"""
            <p style="margin:24px 0;">
                <a href="{reset_url}" style="display:inline-block;padding:12px 20px;background-color:#4f46e5;color:#fff;
                text-decoration:none;border-radius:6px;font-weight:bold;">Reset Password</a>
            </p>
            <p style="font-size:14px;color:#555;">If the button above does not work, copy and paste this link into your browser:<br />
            <span style="word-break:break-all;">{reset_url}</span></p>
        """
    return f"""
        <div style="font-family: Arial, sans-serif; color: #111;">
            <h2 style="margin:0 0 12px;">Reset your CodeSoft password</h2>
            <p style="margin:0 0 16px;">We received a request to reset your password. If you made this request, use the link below to choose a new password.</p>
            {link_html}
            <p style="margin:16px 0 0;font-size:14px;color:#555;">If you did not request a password reset, you can safely ignore this email.</p>
            <hr style="margin:24px 0;border:none;border-top:1px solid #eee;" />
            <p style="font-size:12px;color:#666;">This link will expire in 1 hour for your security.</p>
        </div>
    """


def send_password_reset_email(to_email: str, reset_url: Optional[str]) -> bool:
    """
    Send a password reset email. Returns True if an attempt was made, False otherwise.
    """
    try:
        if not _should_send():
            return False

        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        message = Mail(
            from_email=SENDGRID_FROM_EMAIL,
            to_emails=to_email,
            subject="Reset your CodeSoft password",
            html_content=build_password_reset_html(reset_url),
        )
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        return 200 <= getattr(response, "status_code", 500) < 300
    except Exception as exc:
        logger.exception("Failed to send password reset email: %s", getattr(exc, 'message', str(exc)))
        return False


def build_daily_digest_html(
    violations: List[Any],
    inspections: List[Any],
    complaints: List[Any]
) -> str:
    """
    Builds the HTML content for the daily digest email.
    """
    sections = []

    # Helper to render a list of items
    def render_section(title, items, is_violation=False):
        if not items:
            return ""

        rows = []
        for item in items:
            # Determine address string
            address_str = "No Address"
            if getattr(item, 'address', None):
                address_str = item.address.combadd or "Unknown Address"

            # Determine status/deadline info
            status_info = ""
            row_style = ""

            if is_violation:
                # Check deadline
                deadline_date = getattr(item, 'deadline_date', None)
                if deadline_date and deadline_date < datetime.utcnow():
                    status_info = f"<span style='color: red; font-weight: bold;'>Overdue (Deadline: {deadline_date.strftime('%Y-%m-%d')})</span>"
                else:
                    d_str = deadline_date.strftime('%Y-%m-%d') if deadline_date else "No Deadline"
                    status_info = f"Deadline: {d_str}"

                desc = getattr(item, 'description', 'No Description')
                link = f"{FRONTEND_BASE_URL}/violation/{item.id}" if FRONTEND_BASE_URL else "#"
            else:
                # Inspections / Complaints
                status = getattr(item, 'status', 'Unknown')
                status_info = f"Status: {status}"
                desc = getattr(item, 'description', 'No Description') or getattr(item, 'title', '')
                link = f"{FRONTEND_BASE_URL}/inspection/{item.id}" if FRONTEND_BASE_URL else "#"

            rows.append(f"""
                <div style="margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #eee;">
                    <div style="font-weight: bold; font-size: 14px;">
                        <a href="{link}" style="text-decoration: none; color: #4f46e5;">{address_str}</a>
                    </div>
                    <div style="font-size: 13px; color: #444; margin-top: 4px;">{desc}</div>
                    <div style="font-size: 12px; color: #666; margin-top: 4px;">{status_info}</div>
                </div>
            """)

        return f"""
            <div style="margin-bottom: 24px;">
                <h3 style="margin: 0 0 12px; font-size: 16px; border-bottom: 2px solid #ddd; padding-bottom: 6px;">
                    {title} ({len(items)})
                </h3>
                {''.join(rows)}
            </div>
        """

    if violations:
        sections.append(render_section("Open Violations", violations, is_violation=True))

    if inspections:
        sections.append(render_section("Pending Inspections", inspections))

    if complaints:
        sections.append(render_section("Active Complaints", complaints))

    if not sections:
        return """
            <div style="font-family: Arial, sans-serif; color: #111;">
                <h2 style="margin:0 0 12px;">Daily Morning Digest</h2>
                <p>You have no open items requiring attention today.</p>
                <hr style="margin:24px 0;border:none;border-top:1px solid #eee;" />
                <p style="font-size:12px;color:#666;">This is an automated message from CiviCode.</p>
            </div>
        """

    content = "".join(sections)
    return f"""
        <div style="font-family: Arial, sans-serif; color: #111;">
            <h2 style="margin:0 0 12px;">Daily Morning Digest</h2>
            <p style="margin:0 0 24px;">Here is your summary for today.</p>
            {content}
            <hr style="margin:24px 0;border:none;border-top:1px solid #eee;" />
            <p style="font-size:12px;color:#666;">This is an automated message from CiviCode.</p>
        </div>
    """


def send_daily_digest_email(
    to_email: str,
    violations: List[Any],
    inspections: List[Any],
    complaints: List[Any]
) -> bool:
    """
    Send the daily digest email.
    """
    try:
        if not _should_send():
            return False

        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        html_content = build_daily_digest_html(violations, inspections, complaints)
        message = Mail(
            from_email=SENDGRID_FROM_EMAIL,
            to_emails=to_email,
            subject="Your Daily CiviCode Digest",
            html_content=html_content,
        )
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        return 200 <= getattr(response, "status_code", 500) < 300
    except Exception as exc:
        logger.exception("Failed to send daily digest email: %s", getattr(exc, 'message', str(exc)))
        return False
