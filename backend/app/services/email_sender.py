import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings


def send_otp(email: str, otp: str) -> None:
    # If SMTP_USER is empty, print to server console (dev mode)
    if not settings.SMTP_USER:
        print("\n" + "=" * 50)
        print(f"[DEV MODE] OTP for {email}: {otp}")
        print("=" * 50 + "\n", flush=True)
        return

    msg = MIMEMultipart()
    msg["From"] = settings.SMTP_USER
    msg["To"] = email
    msg["Subject"] = "Your CivicQuest Verification Code"

    body = f"Hello,\n\nYour one-time verification code for CivicQuest is: {otp}\n\nThis code expires in 5 minutes.\n\nThank you!"
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
