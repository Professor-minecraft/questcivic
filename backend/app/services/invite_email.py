import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings


def send_invite_email(email: str, token: str) -> bool:
    """
    Send an invitation email to the auditor with a link to set their password.
    Returns True if sent (or printed in dev mode), False if sending fails.
    """
    link = f"{settings.frontend_base_url}/auditor/set-password?token={token}"

    # If SMTP_USER is empty, print to server console (dev mode)
    if not settings.SMTP_USER:
        print("\n" + "=" * 50)
        print(f"[DEV MODE] Auditor invite link for {email}: {link}")
        print("=" * 50 + "\n", flush=True)
        return True

    msg = MIMEMultipart()
    msg["From"] = settings.SMTP_USER
    msg["To"] = email
    msg["Subject"] = "CivicQuest auditor account: set your password"

    body = (
        f"Hello,\n\n"
        f"You have been invited as an auditor for CivicQuest.\n"
        f"Please set your password using the link below:\n\n"
        f"{link}\n\n"
        f"This link expires in {settings.INVITE_EXPIRE_HOURS} hours.\n\n"
        f"Thank you!"
    )
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send auditor invite email to {email}: {e}", flush=True)
        return False
