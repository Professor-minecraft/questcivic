import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
import httpx
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)


def _sanitize_log_message(msg: str) -> str:
    """Ensure sensitive data like API keys are not in log outputs."""
    if settings.EMAIL_API_KEY and len(settings.EMAIL_API_KEY) > 4:
        msg = msg.replace(settings.EMAIL_API_KEY, "[REDACTED]")
    if settings.SMTP_PASSWORD and len(settings.SMTP_PASSWORD) > 4:
        msg = msg.replace(settings.SMTP_PASSWORD, "[REDACTED]")
    return msg


def _send_smtp(to_email: str, subject: str, body: str, html_body: Optional[str] = None) -> None:
    from_address = settings.EMAIL_FROM_ADDRESS or settings.SMTP_USER
    msg = MIMEMultipart("alternative")
    if settings.EMAIL_FROM_NAME:
        msg["From"] = f"{settings.EMAIL_FROM_NAME} <{from_address}>"
    else:
        msg["From"] = from_address
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))
    if html_body:
        msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10.0) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as exc:
        sanitized = _sanitize_log_message(str(exc))
        logger.error(f"[EMAIL ERROR] SMTP delivery to {to_email} failed: {sanitized}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send email. Please try again later.",
        ) from None


def _send_brevo(to_email: str, subject: str, body: str, html_body: Optional[str] = None) -> None:
    sender_name = settings.EMAIL_FROM_NAME or "CivicQuest"
    sender_email = settings.EMAIL_FROM_ADDRESS or settings.SMTP_USER
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "api-key": settings.EMAIL_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "sender": {
            "name": sender_name,
            "email": sender_email,
        },
        "to": [
            {"email": to_email}
        ],
        "subject": subject,
        "textContent": body,
    }
    if html_body:
        payload["htmlContent"] = html_body

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException:
        logger.error(f"[EMAIL ERROR] Brevo API timed out after 10 seconds while sending to {to_email}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send email due to a provider timeout. Please try again later.",
        ) from None
    except httpx.RequestError as exc:
        logger.error(f"[EMAIL ERROR] Brevo request failed: {type(exc).__name__}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send email. Please try again later.",
        ) from None

    if response.status_code >= 400:
        error_msg = _sanitize_log_message(response.text)
        logger.error(f"[EMAIL ERROR] Brevo returned status {response.status_code}: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send email. Please try again later.",
        )


def _send_resend(to_email: str, subject: str, body: str, html_body: Optional[str] = None) -> None:
    sender_name = settings.EMAIL_FROM_NAME or "CivicQuest"
    sender_email = settings.EMAIL_FROM_ADDRESS or settings.SMTP_USER
    from_str = f"{sender_name} <{sender_email}>" if sender_name else sender_email
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {settings.EMAIL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "from": from_str,
        "to": [to_email],
        "subject": subject,
        "text": body,
    }
    if html_body:
        payload["html"] = html_body

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException:
        logger.error(f"[EMAIL ERROR] Resend API timed out after 10 seconds while sending to {to_email}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send email due to a provider timeout. Please try again later.",
        ) from None
    except httpx.RequestError as exc:
        logger.error(f"[EMAIL ERROR] Resend request failed: {type(exc).__name__}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send email. Please try again later.",
        ) from None

    if response.status_code >= 400:
        error_msg = _sanitize_log_message(response.text)
        logger.error(f"[EMAIL ERROR] Resend returned status {response.status_code}: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send email. Please try again later.",
        )


def send_email(to_email: str, subject: str, body: str, html_body: Optional[str] = None) -> None:
    """Unified email sender supporting SMTP, Brevo, and Resend backends."""
    backend = settings.EMAIL_BACKEND.lower()

    # Dev mode / unconfigured fallback: print to console
    if backend == "smtp" and not settings.SMTP_USER:
        print("\n" + "=" * 50)
        print(f"[DEV MODE] Email to {to_email}:")
        print(f"Subject: {subject}")
        print(f"Body:\n{body}")
        print("=" * 50 + "\n", flush=True)
        return

    if backend in ("brevo", "resend") and not settings.EMAIL_API_KEY and settings.ENVIRONMENT.lower() == "development":
        print("\n" + "=" * 50)
        print(f"[DEV MODE ({backend.upper()})] Email to {to_email}:")
        print(f"Subject: {subject}")
        print(f"Body:\n{body}")
        print("=" * 50 + "\n", flush=True)
        return

    if backend == "smtp":
        _send_smtp(to_email, subject, body, html_body)
    elif backend == "brevo":
        _send_brevo(to_email, subject, body, html_body)
    elif backend == "resend":
        _send_resend(to_email, subject, body, html_body)
    else:
        logger.error(f"[EMAIL ERROR] Unknown EMAIL_BACKEND: {backend}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid email backend configuration.",
        )


def send_otp(email: str, otp: str) -> None:
    # If in dev mode with SMTP and no SMTP_USER, preserve the exact test log format
    if settings.EMAIL_BACKEND.lower() == "smtp" and not settings.SMTP_USER:
        print("\n" + "=" * 50)
        print(f"[DEV MODE] OTP for {email}: {otp}")
        print("=" * 50 + "\n", flush=True)
        return

    if settings.EMAIL_BACKEND.lower() in ("brevo", "resend") and not settings.EMAIL_API_KEY and settings.ENVIRONMENT.lower() == "development":
        print("\n" + "=" * 50)
        print(f"[DEV MODE] OTP for {email}: {otp}")
        print("=" * 50 + "\n", flush=True)
        return

    subject = "Your CivicQuest Verification Code"
    body = (
        f"Hello,\n\n"
        f"Your one-time verification code for CivicQuest is: {otp}\n\n"
        f"This code expires in {settings.OTP_EXPIRE_MINUTES} minutes.\n\n"
        f"Thank you!"
    )
    send_email(email, subject, body)
