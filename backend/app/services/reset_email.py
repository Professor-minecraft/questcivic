from app.config import settings
from app.services.email_sender import send_email


def send_password_reset_email(email: str, code: str) -> None:
    """Send a password reset OTP email or print to console in dev mode."""
    reset_page = f"{settings.frontend_base_url}/reset-password"
    if (settings.EMAIL_BACKEND.lower() == "smtp" and not settings.SMTP_USER) or (
        settings.EMAIL_BACKEND.lower() in ("brevo", "resend")
        and not settings.EMAIL_API_KEY
        and settings.ENVIRONMENT.lower() == "development"
    ):
        print("\n" + "=" * 50)
        print(f"[DEV MODE] Password reset code for {email}: {code}")
        print(f"[DEV MODE] Password reset page: {reset_page}")
        print(f"[DEV MODE] This code is valid for {settings.OTP_EXPIRE_MINUTES} minutes.")
        print("[DEV MODE] If you did not request a password reset, please ignore this email.")
        print("=" * 50 + "\n", flush=True)
        return

    subject = "CivicQuest password reset code"
    body = (
        f"Hello,\n\n"
        f"Your CivicQuest password reset code is: {code}\n\n"
        f"Enter this code on the password reset page: {reset_page}\n\n"
        f"This code is valid for {settings.OTP_EXPIRE_MINUTES} minutes.\n\n"
        f"If you did not request a password reset, please ignore this email.\n\n"
        f"Thank you!"
    )
    send_email(email, subject, body)


def send_password_changed_notice(email: str) -> None:
    """Send a notice email that password was changed."""
    login_page = f"{settings.frontend_base_url}/login"
    if (settings.EMAIL_BACKEND.lower() == "smtp" and not settings.SMTP_USER) or (
        settings.EMAIL_BACKEND.lower() in ("brevo", "resend")
        and not settings.EMAIL_API_KEY
        and settings.ENVIRONMENT.lower() == "development"
    ):
        print("\n" + "=" * 50)
        print(f"[DEV MODE] Notice: Password was changed for {email}")
        print(f"[DEV MODE] Login page: {login_page}")
        print("=" * 50 + "\n", flush=True)
        return

    subject = "Your CivicQuest password was changed"
    body = (
        f"Hello,\n\n"
        f"This is a confirmation that your CivicQuest account password has been successfully changed.\n\n"
        f"You can log in at: {login_page}\n\n"
        f"If you did not make this change, please contact support immediately.\n\n"
        f"Thank you!"
    )
    send_email(email, subject, body)
