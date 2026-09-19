from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
import pyotp
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import OTPRequest, PendingSignup, User
from app.security import create_token
from app.services.email_sender import send_otp
from app.services.passwords import hash_password, validate_password

router = APIRouter(prefix="/auth/signup", tags=["signup"])


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str


class ResendOTPRequest(BaseModel):
    email: str


class VerifySignupRequest(BaseModel):
    email: str
    otp: str


class SignupUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    constituency: Optional[str] = None
    xp: int = 0


class SignupVerifyResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: SignupUserResponse


def normalize_and_validate_email(email: str) -> str:
    normalized = email.strip().lower()
    allowed_domain = settings.ALLOWED_EMAIL_DOMAIN.strip().lower()
    if not normalized.endswith(f"@{allowed_domain}"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only @{allowed_domain} email addresses are allowed.",
        )
    return normalized


def check_otp_rate_limits(db: Session, email: str, now: datetime) -> None:
    # 60 seconds cooldown between sends
    cooldown_cutoff = now - timedelta(seconds=60)
    recent_otp = (
        db.query(OTPRequest)
        .filter(
            OTPRequest.email == email,
            OTPRequest.purpose == "signup",
            OTPRequest.created_at >= cooldown_cutoff,
        )
        .first()
    )
    if recent_otp:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait 60 seconds before requesting another code.",
        )

    # Max 5 signup codes per email per hour
    hour_cutoff = now - timedelta(hours=1)
    hourly_count = (
        db.query(OTPRequest)
        .filter(
            OTPRequest.email == email,
            OTPRequest.purpose == "signup",
            OTPRequest.created_at >= hour_cutoff,
        )
        .count()
    )
    if hourly_count >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many signup attempts. Please try again later.",
        )


@router.post("", status_code=status.HTTP_200_OK)
def signup(req: SignupRequest, request: Request, db: Session = Depends(get_db)):
    # 1. Validate name: collapse repeated spaces, 2 to 60 characters, allowed characters
    import unicodedata

    name = " ".join(req.name.strip().split())
    if len(name) < 2 or len(name) > 60:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name must be between 2 and 60 characters long.",
        )

    allowed_special = {" ", ".", "-", "'", "’"}
    valid_chars = all(
        c in allowed_special
        or unicodedata.category(c).startswith("L")
        or unicodedata.category(c).startswith("M")
        for c in name
    )
    has_letter = any(unicodedata.category(c).startswith("L") for c in name)

    if not valid_chars or not has_letter:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name can only contain letters, spaces, dots, hyphens, and apostrophes.",
        )

    # 2. Normalize and validate email domain
    email = normalize_and_validate_email(req.email)

    # 3. Check existing verified user
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        if existing_user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists. Please log in.",
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "code": "legacy_account",
                    "message": "This account already exists. Use Forgot password to set a password.",
                    "detail": "This account already exists. Use Forgot password to set a password.",
                },
            )

    # 4. Validate password
    pwd_error = validate_password(req.password, email)
    if pwd_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=pwd_error,
        )

    now = datetime.utcnow()

    # 5. Check rate limits
    check_otp_rate_limits(db, email, now)

    # 6. Save or replace row in pending_signups (with bcrypt hash)
    pwd_hash = hash_password(req.password)
    pending = db.query(PendingSignup).filter(PendingSignup.email == email).first()
    if pending:
        pending.name = name
        pending.password_hash = pwd_hash
        pending.created_at = now
    else:
        pending = PendingSignup(
            email=email,
            name=name,
            password_hash=pwd_hash,
            created_at=now,
        )
        db.add(pending)

    # 7. Create OTP request
    secret = pyotp.random_base32()
    code = pyotp.TOTP(secret, digits=6, interval=settings.OTP_EXPIRE_MINUTES * 60).now()
    expires_at = now + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
    client_ip = request.client.host if request.client else None

    otp_req = OTPRequest(
        email=email,
        purpose="signup",
        otp_secret=secret,
        attempts=0,
        used=False,
        ip=client_ip,
        created_at=now,
        expires_at=expires_at,
    )
    db.add(otp_req)

    # 8. Send OTP email before committing (rollback on failure)
    try:
        send_otp(email, code)
    except Exception:
        db.rollback()
        raise

    db.commit()

    return {"message": "OTP sent"}


@router.post("/resend-otp", status_code=status.HTTP_200_OK)
def resend_otp(req: ResendOTPRequest, request: Request, db: Session = Depends(get_db)):
    email = normalize_and_validate_email(req.email)

    # Check pending signup exists
    pending = db.query(PendingSignup).filter(PendingSignup.email == email).first()
    if not pending:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending signup found for this email.",
        )

    now = datetime.utcnow()

    # Check rate limits
    check_otp_rate_limits(db, email, now)

    # Create new OTP request
    secret = pyotp.random_base32()
    code = pyotp.TOTP(secret, digits=6, interval=settings.OTP_EXPIRE_MINUTES * 60).now()
    expires_at = now + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
    client_ip = request.client.host if request.client else None

    otp_req = OTPRequest(
        email=email,
        purpose="signup",
        otp_secret=secret,
        attempts=0,
        used=False,
        ip=client_ip,
        created_at=now,
        expires_at=expires_at,
    )
    db.add(otp_req)

    try:
        send_otp(email, code)
    except Exception:
        db.rollback()
        raise

    db.commit()

    return {"message": "OTP sent"}


@router.post("/verify", response_model=SignupVerifyResponse, status_code=status.HTTP_200_OK)
def verify_signup(req: VerifySignupRequest, db: Session = Depends(get_db)):
    email = normalize_and_validate_email(req.email)
    otp = req.otp.strip()

    now = datetime.utcnow()

    # Fetch latest unused signup OTP request
    otp_req = (
        db.query(OTPRequest)
        .filter(
            OTPRequest.email == email,
            OTPRequest.purpose == "signup",
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

    pending = db.query(PendingSignup).filter(PendingSignup.email == email).first()
    if not pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending signup found for this email.",
        )

    totp = pyotp.TOTP(
        otp_req.otp_secret,
        digits=6,
        interval=settings.OTP_EXPIRE_MINUTES * 60,
    )
    if not totp.verify(otp, valid_window=0):
        otp_req.attempts += 1
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid code",
        )

    # OTP is valid
    otp_req.used = True

    new_otp_secret = pyotp.random_base32()
    user = User(
        email=email,
        name=pending.name,
        password_hash=pending.password_hash,
        email_verified=1,
        xp=0,
        otp_secret=new_otp_secret,
        created_at=now,
    )
    db.add(user)
    db.delete(pending)
    db.commit()
    db.refresh(user)

    token = create_token(sub=str(user.id), role="user")
    return SignupVerifyResponse(
        access_token=token,
        token_type="bearer",
        user=SignupUserResponse.model_validate(user),
    )
