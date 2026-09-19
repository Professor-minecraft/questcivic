import logging
from app.config import settings
from app.services.email_sender import send_email

logger = logging.getLogger(__name__)


def send_invite_email(email: str, token: str) -> bool:
    """
    Send an invitation email to the auditor with a link to set their password.
    Returns True if sent (or printed in dev mode), False if sending fails.
    """
    link = f"{settings.frontend_base_url}/auditor/set-password?token={token}"

    # If in dev mode with SMTP and no SMTP_USER, print to server console
    if (settings.EMAIL_BACKEND.lower() == "smtp" and not settings.SMTP_USER) or (
        settings.EMAIL_BACKEND.lower() in ("brevo", "resend")
        and not settings.EMAIL_API_KEY
        and settings.ENVIRONMENT.lower() == "development"
    ):
        print("\n" + "=" * 50)
        print(f"[DEV MODE] Auditor invite link for {email}: {link}")
        print("=" * 50 + "\n", flush=True)
        return True

    subject = "CivicQuest auditor account: set your password"
    body = (
        f"Hello,\n\n"
        f"You have been invited as an auditor for CivicQuest.\n"
        f"Please set your password using the link below:\n\n"
        f"{link}\n\n"
        f"This link expires in {settings.INVITE_EXPIRE_HOURS} hours.\n\n"
        f"Thank you!"
    )

    try:
        send_email(email, subject, body)
        return True
    except Exception as e:
        logger.error(f"[ERROR] Failed to send auditor invite email to {email}: {e}")
        return False
