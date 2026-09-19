from datetime import date, datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.services.normalize import normalize_place

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
    if not settings.LEGACY_OTP_LOGIN_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not available",
        )
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
    if not settings.LEGACY_OTP_LOGIN_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not available",
        )
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
    # Respect the kill-switch: when the built-in auditor is disabled, return 401.
    if not settings.BUILTIN_AUDITOR_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid auditor username or password.",
        )
    if req.username != settings.AUDITOR_ID or not verify_auditor_password(req.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid auditor username or password.",
        )
    token = create_token(sub=settings.AUDITOR_ID, role="auditor")
    return AuditorLoginResponse(access_token=token)


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    state: Optional[str] = None
    district: Optional[str] = None
    constituency: Optional[str] = None
    xp: int = 0
    location_locked_until: Optional[date] = None


@me_router.get("", response_model=MeResponse)
def get_me(
    current_user: User = Depends(get_current_user),
):
    locked_until: Optional[date] = None
    if settings.LOCATION_CHANGE_DAYS > 0 and current_user.location_changed_at is not None:
        if current_user.state and current_user.district:
            loc_dt = current_user.location_changed_at
            if loc_dt.tzinfo is not None:
                elapsed = datetime.now(timezone.utc) - loc_dt
            else:
                elapsed = datetime.utcnow() - loc_dt

            # Change allowed if within 15 mins (typo grace) or >= LOCATION_CHANGE_DAYS
            if elapsed > timedelta(minutes=15) and elapsed < timedelta(days=settings.LOCATION_CHANGE_DAYS):
                locked_until = (loc_dt + timedelta(days=settings.LOCATION_CHANGE_DAYS)).date()

    return MeResponse(
        id=current_user.id,
        email=current_user.email,
        state=current_user.state,
        district=current_user.district,
        constituency=current_user.constituency,
        xp=current_user.xp,
        location_locked_until=locked_until,
    )


@me_router.put("/location", response_model=UserResponse)
def update_location(
    req: UpdateLocationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()

    new_state_norm = normalize_place(req.state)
    new_district_norm = normalize_place(req.district)
    new_constituency_norm = normalize_place(req.constituency)

    saved_state_norm = normalize_place(current_user.state)
    saved_district_norm = normalize_place(current_user.district)
    saved_constituency_norm = normalize_place(current_user.constituency)

    has_saved_location = bool(saved_state_norm and saved_district_norm)

    # 1. If the user has no saved location yet, allow it and set location_changed_at = now
    if not has_saved_location:
        current_user.state = req.state.strip()
        current_user.district = req.district.strip()
        current_user.constituency = req.constituency.strip() if req.constituency else None
        current_user.location_changed_at = now
        db.commit()
        db.refresh(current_user)
        return current_user

    # 2. If new state, district and constituency are the same as the saved ones,
    # return the user unchanged and do not touch location_changed_at
    if (
        new_state_norm == saved_state_norm
        and new_district_norm == saved_district_norm
        and new_constituency_norm == saved_constituency_norm
    ):
        return current_user

    # 3. If the location is different:
    # allow when location_changed_at is empty, or within 15 minutes, or older than LOCATION_CHANGE_DAYS days
    if current_user.location_changed_at is None:
        allowed = True
    elif settings.LOCATION_CHANGE_DAYS == 0:
        allowed = True
    else:
        loc_dt = current_user.location_changed_at
        if loc_dt.tzinfo is not None:
            elapsed = datetime.now(timezone.utc) - loc_dt
        else:
            elapsed = now - loc_dt
        allowed = (
            elapsed <= timedelta(minutes=15)
            or elapsed >= timedelta(days=settings.LOCATION_CHANGE_DAYS)
        )

    if allowed:
        current_user.state = req.state.strip()
        current_user.district = req.district.strip()
        current_user.constituency = req.constituency.strip() if req.constituency else None
        current_user.location_changed_at = now
        db.commit()
        db.refresh(current_user)
        return current_user

    next_date = (current_user.location_changed_at + timedelta(days=settings.LOCATION_CHANGE_DAYS)).date()
    msg = f"You can change your location once every {settings.LOCATION_CHANGE_DAYS} days. Next change on {next_date}."
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "message": msg,
            "detail": msg,
        },
    )
