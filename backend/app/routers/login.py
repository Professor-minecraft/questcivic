from datetime import datetime, timedelta
import math
from threading import Lock
from typing import Optional, Tuple
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.security import create_token
from app.services.passwords import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# In-memory rate-limiter: key -> (fail_count, last_failed_at, locked_until)
# ---------------------------------------------------------------------------
_rate_lock = Lock()
_fail_tracker: dict[str, Tuple[int, datetime, Optional[datetime]]] = {}

# Precomputed dummy bcrypt hash for timing safety against user enumeration
_DUMMY_HASH = bcrypt.hashpw(b"dummy_password_for_timing_safety", bcrypt.gensalt()).decode("utf-8")


def _check_rate_limit(key: str, now: datetime) -> None:
    with _rate_lock:
        entry = _fail_tracker.get(key)
        if not entry:
            return
        count, last_failed_at, locked_until = entry
        if locked_until:
            if now < locked_until:
                remaining_seconds = (locked_until - now).total_seconds()
                rem_mins = max(1, int(math.ceil(remaining_seconds / 60.0)))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many attempts. Try again in {rem_mins} minutes.",
                )
            else:
                # Lockout has expired, clear entry
                _fail_tracker.pop(key, None)
        elif (now - last_failed_at) > timedelta(minutes=settings.LOGIN_LOCK_MINUTES):
            # Old failure window expired
            _fail_tracker.pop(key, None)


def _record_failure(key: str, now: datetime) -> None:
    with _rate_lock:
        entry = _fail_tracker.get(key)
        if entry:
            prev_count, prev_last_failed_at, prev_locked_until = entry
            if (now - prev_last_failed_at) <= timedelta(minutes=settings.LOGIN_LOCK_MINUTES):
                count = prev_count + 1
            else:
                count = 1
        else:
            count = 1

        locked_until = (
            now + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
            if count >= settings.LOGIN_MAX_ATTEMPTS
            else None
        )
        _fail_tracker[key] = (count, now, locked_until)


def _clear_email_fails(email: str) -> None:
    key = f"email:{email.strip().lower()}"
    with _rate_lock:
        _fail_tracker.pop(key, None)


def reset_login_rate_limits() -> None:
    """Helper to reset in-memory login rate limit tracker (e.g. for testing)."""
    with _rate_lock:
        _fail_tracker.clear()


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    constituency: Optional[str] = None
    xp: int = 0


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: LoginUserResponse


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = req.email.strip().lower()
    client_ip = request.client.host if request.client else None
    now = datetime.utcnow()

    # 1. Check rate limits (email and IP)
    _check_rate_limit(f"email:{email}", now)
    if client_ip:
        _check_rate_limit(f"ip:{client_ip}", now)

    # 2. Check user and password
    user = db.query(User).filter(User.email == email).first()

    login_failed = False
    if not user:
        verify_password(req.password, _DUMMY_HASH)
        login_failed = True
    elif not user.password_hash:
        verify_password(req.password, _DUMMY_HASH)
        login_failed = True
    elif not user.email_verified:
        verify_password(req.password, _DUMMY_HASH)
        login_failed = True
    else:
        if not verify_password(req.password, user.password_hash):
            login_failed = True

    if login_failed:
        fail_now = datetime.utcnow()
        _record_failure(f"email:{email}", fail_now)
        if client_ip:
            _record_failure(f"ip:{client_ip}", fail_now)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. If you have not set a password yet, use Forgot password.",
        )

    # 3. Successful login: clear email fails counter
    _clear_email_fails(email)

    token = create_token(sub=str(user.id), role="user")
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=LoginUserResponse.model_validate(user),
    )
