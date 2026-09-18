from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import (
    AuditorLoginRequest,
    AuditorLoginResponse,
    RequestOTPRequest,
    RequestOTPResponse,
    UpdateLocationRequest,
    UserResponse,
    VerifyOTPRequest,
    VerifyOTPResponse,
)
from app.security import create_token, get_current_user, verify_auditor_password
from app.services.email_sender import send_otp
from app.services.otp import (
    check_can_request_otp,
    generate_otp_code,
    get_or_create_pending_secret,
    get_pending_secret,
    verify_otp_code,
)

auth_router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(prefix="/me", tags=["me"])


def validate_email_domain(email: str) -> str:
    normalized = email.strip().lower()
    allowed_domain = settings.ALLOWED_EMAIL_DOMAIN.strip().lower()
    if not normalized.endswith(f"@{allowed_domain}"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only @{allowed_domain} email addresses are allowed.",
        )
    return normalized


@auth_router.post("/request-otp", response_model=RequestOTPResponse)
def request_otp(
    req: RequestOTPRequest,
    db: Session = Depends(get_db),
):
    email = validate_email_domain(req.email)
    check_can_request_otp(email)

    user = db.query(User).filter(User.email == email).first()
    secret = get_or_create_pending_secret(email, user.otp_secret if user else None)
    otp = generate_otp_code(secret)

    send_otp(email, otp)
    return RequestOTPResponse(message="OTP sent")


@auth_router.post("/verify-otp", response_model=VerifyOTPResponse)
def verify_otp(
    req: VerifyOTPRequest,
    db: Session = Depends(get_db),
):
    email = validate_email_domain(req.email)

    user = db.query(User).filter(User.email == email).first()
    secret = user.otp_secret if user else get_pending_secret(email)
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OTP requested for this email.",
        )

    # Verifies OTP or raises 400/429
    verify_otp_code(email, secret, req.otp)

    # Create user if new
    if not user:
        user = User(
            email=email,
            otp_secret=secret,
            xp=0,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_token(sub=str(user.id), role="user")
    return VerifyOTPResponse(access_token=token, user=user)


@auth_router.post("/auditor-login", response_model=AuditorLoginResponse)
def auditor_login(req: AuditorLoginRequest):
    if req.username != settings.AUDITOR_ID or not verify_auditor_password(req.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid auditor username or password.",
        )
    token = create_token(sub=settings.AUDITOR_ID, role="auditor")
    return AuditorLoginResponse(access_token=token)


@me_router.get("", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user


@me_router.put("/location", response_model=UserResponse)
def update_location(
    req: UpdateLocationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.state = req.state.strip()
    current_user.district = req.district.strip()
    current_user.constituency = req.constituency.strip() if req.constituency else None

    db.commit()
    db.refresh(current_user)
    return current_user
