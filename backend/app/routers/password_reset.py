from datetime import datetime, timedelta
import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import pyotp
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import OTPRequest, User
from app.services.passwords import hash_password, validate_password
from app.services.reset_email import send_password_changed_notice, send_password_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str


def validate_email_format(email: str) -> str:
    normalized = email.strip().lower()
    allowed_domain = settings.ALLOWED_EMAIL_DOMAIN.strip().lower()
    if not normalized.endswith(f"@{allowed_domain}"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only @{allowed_domain} email addresses are allowed.",
        )
    return normalized


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(req: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    email = validate_email_format(req.email)
    client_ip = request.client.host if request.client else None
    now = datetime.utcnow()

    # 1) 60-second cooldown check: do NOT create new OTP request on double-tap
    cooldown_cutoff = now - timedelta(seconds=60)
    recent_req = (
        db.query(OTPRequest)
        .filter(
            OTPRequest.email == email,
            OTPRequest.purpose == "reset",
            OTPRequest.created_at >= cooldown_cutoff,
        )
        .order_by(OTPRequest.created_at.desc())
        .first()
    )
    if recent_req:
        elapsed = (now - recent_req.created_at).total_seconds()
        retry_after = max(1, int(math.ceil(60.0 - elapsed)))
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "message": f"Please wait {retry_after} seconds before requesting another reset code.",
                "retry_after_seconds": retry_after,
                "detail": f"Please wait {retry_after} seconds before requesting another reset code.",
            },
        )

    # 2) Daily limit: count requests for this email created in the last 24 hours
    window_24h = now - timedelta(hours=24)
    email_requests_24h = (
        db.query(OTPRequest)
        .filter(
            OTPRequest.email == email,
            OTPRequest.purpose == "reset",
            OTPRequest.created_at >= window_24h,
        )
        .order_by(OTPRequest.created_at.asc())
        .all()
    )
    if len(email_requests_24h) >= settings.RESET_REQUESTS_PER_DAY:
        oldest_req = email_requests_24h[0]
        reset_time = oldest_req.created_at + timedelta(hours=24)
        retry_after_seconds = max(1, int(math.ceil((reset_time - now).total_seconds())))
        time_str = reset_time.strftime("%Y-%m-%d %H:%M:%S UTC")
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "message": f"You can request a password reset only {settings.RESET_REQUESTS_PER_DAY} times in 24 hours. Try again after {time_str}.",
                "retry_after_seconds": retry_after_seconds,
                "detail": f"You can request a password reset only {settings.RESET_REQUESTS_PER_DAY} times in 24 hours. Try again after {time_str}.",
            },
        )

    # 3) IP limit: at most 10 reset requests per IP per 24 hours
    if client_ip:
        ip_requests_24h = (
            db.query(OTPRequest)
            .filter(
                OTPRequest.ip == client_ip,
                OTPRequest.purpose == "reset",
                OTPRequest.created_at >= window_24h,
            )
            .order_by(OTPRequest.created_at.asc())
            .all()
        )
        if len(ip_requests_24h) >= 10:
            oldest_ip_req = ip_requests_24h[0]
            ip_reset_time = oldest_ip_req.created_at + timedelta(hours=24)
            ip_retry_after = max(1, int(math.ceil((ip_reset_time - now).total_seconds())))
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "message": "Too many password reset requests from this IP. Try again later.",
                    "retry_after_seconds": ip_retry_after,
                    "detail": "Too many password reset requests from this IP. Try again later.",
                },
            )

    # 4) Create an otp_requests row ALWAYS, even when email is not registered
    secret = pyotp.random_base32()
    code = pyotp.TOTP(secret, digits=6, interval=settings.OTP_EXPIRE_MINUTES * 60).now()
    expires_at = now + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)

    otp_req = OTPRequest(
        email=email,
        purpose="reset",
        otp_secret=secret,
        attempts=0,
        used=False,
        ip=client_ip,
        created_at=now,
        expires_at=expires_at,
    )
    db.add(otp_req)
    db.commit()

    # 5) Only if a verified user with this email exists: send email
    user = db.query(User).filter(User.email == email, User.email_verified == 1).first()
    if user:
        send_password_reset_email(email, code)

    # 6) Response is always 200 with remaining count, same for registered and unknown
    remaining = max(0, settings.RESET_REQUESTS_PER_DAY - (len(email_requests_24h) + 1))
    return {
        "message": "If this email is registered, a reset code has been sent.",
        "remaining_requests_today": remaining,
    }


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    email = req.email.strip().lower()
    otp = req.otp.strip()
    now = datetime.utcnow()

    # Use the latest unused, unexpired reset request for this email
    otp_req = (
        db.query(OTPRequest)
        .filter(
            OTPRequest.email == email,
            OTPRequest.purpose == "reset",
            OTPRequest.used == False,
        )
        .order_by(OTPRequest.created_at.desc(), OTPRequest.id.desc())
        .first()
    )

    if not otp_req or otp_req.expires_at <= now or otp_req.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code expired. Request a new one.",
        )

    # Verify user exists and is verified
    user = db.query(User).filter(User.email == email).first()

    totp = pyotp.TOTP(
        otp_req.otp_secret,
        digits=6,
        interval=settings.OTP_EXPIRE_MINUTES * 60,
    )
    is_valid_code = totp.verify(otp, valid_window=0)

    # Wrong code or unknown email adds 1 to attempts and returns 400 "Invalid code"
    if not user or not user.email_verified or not is_valid_code:
        otp_req.attempts += 1
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid code",
        )

    # Validate the new password
    pwd_error = validate_password(req.new_password, email)
    if pwd_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=pwd_error,
        )

    # Update password and timestamps
    user.password_hash = hash_password(req.new_password)
    user.password_changed_at = now
    user.email_verified = 1

    # Mark this request used, and mark every other unused reset request for this email used
    otp_req.used = True
    db.query(OTPRequest).filter(
        OTPRequest.email == email,
        OTPRequest.purpose == "reset",
        OTPRequest.used == False,
    ).update({"used": True})

    db.commit()

    # Send notice email (ignore failure)
    try:
        send_password_changed_notice(email)
    except Exception:
        pass

    return {"message": "Password updated. Please log in."}
