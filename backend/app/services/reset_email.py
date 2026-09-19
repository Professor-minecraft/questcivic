import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings


def send_password_reset_email(email: str, code: str) -> None:
    """Send a password reset OTP email or print to console in dev mode."""
    reset_page = f"{settings.frontend_base_url}/reset-password"
    if not settings.SMTP_USER:
        print("\n" + "=" * 50)
        print(f"[DEV MODE] Password reset code for {email}: {code}")
        print(f"[DEV MODE] Password reset page: {reset_page}")
        print(f"[DEV MODE] This code is valid for {settings.OTP_EXPIRE_MINUTES} minutes.")
        print("[DEV MODE] If you did not request a password reset, please ignore this email.")
        print("=" * 50 + "\n", flush=True)
        return

    msg = MIMEMultipart()
    msg["From"] = settings.SMTP_USER
    msg["To"] = email
    msg["Subject"] = "CivicQuest password reset code"

    body = (
        f"Hello,\n\n"
        f"Your CivicQuest password reset code is: {code}\n\n"
        f"Enter this code on the password reset page: {reset_page}\n\n"
        f"This code is valid for {settings.OTP_EXPIRE_MINUTES} minutes.\n\n"
        f"If you did not request a password reset, please ignore this email.\n\n"
        f"Thank you!"
    )
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)


def send_password_changed_notice(email: str) -> None:
    """Send a notice email that password was changed."""
    login_page = f"{settings.frontend_base_url}/login"
    if not settings.SMTP_USER:
        print("\n" + "=" * 50)
        print(f"[DEV MODE] Notice: Password was changed for {email}")
        print(f"[DEV MODE] Login page: {login_page}")
        print("=" * 50 + "\n", flush=True)
        return

    msg = MIMEMultipart()
    msg["From"] = settings.SMTP_USER
    msg["To"] = email
    msg["Subject"] = "Your CivicQuest password was changed"

    body = (
        f"Hello,\n\n"
        f"This is a confirmation that your CivicQuest account password has been successfully changed.\n\n"
        f"You can log in at: {login_page}\n\n"
        f"If you did not make this change, please contact support immediately.\n\n"
        f"Thank you!"
    )
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
