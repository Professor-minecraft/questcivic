"""
POST /auth/staff-login

Unified login for:
  - Admin  (ADMIN_ID + ADMIN_PASSWORD)  → role "admin"
  - Built-in auditor (AUDITOR_ID + AUDITOR_PASSWORD) → role "auditor"
  - DB auditor (email + password_hash)  → role "auditor" + auditor_id claim

Rate-limit: 5 wrong attempts per username → 15-minute lockout (in-memory).
"""

from datetime import datetime, timedelta
from threading import Lock
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Auditor
from app.security import (
    create_token,
    verify_auditor_password,
    verify_admin_password,
)

import bcrypt

router = APIRouter(prefix="/auth", tags=["staff-auth"])

# ---------------------------------------------------------------------------
# In-memory rate-limiter: {username_lower: (fail_count, lockout_until | None)}
# ---------------------------------------------------------------------------
_rate_lock = Lock()
_fail_tracker: dict[str, tuple[int, Optional[datetime]]] = {}

MAX_FAILS = 5
LOCKOUT_MINUTES = 15


def _check_rate_limit(username: str) -> None:
    """Raise 429 if the username is currently locked out."""
    key = username.strip().lower()
    with _rate_lock:
        entry = _fail_tracker.get(key)
        if entry is None:
            return
        count, locked_until = entry
        if locked_until and datetime.utcnow() < locked_until:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Too many failed attempts. "
                    f"Try again after {LOCKOUT_MINUTES} minutes."
                ),
            )
        # Lockout expired – clear it
        if locked_until and datetime.utcnow() >= locked_until:
            del _fail_tracker[key]


def _record_fail(username: str) -> None:
    key = username.strip().lower()
    with _rate_lock:
        entry = _fail_tracker.get(key, (0, None))
        count = entry[0] + 1
        locked_until = (
            datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
            if count >= MAX_FAILS
            else None
        )
        _fail_tracker[key] = (count, locked_until)


def _clear_fails(username: str) -> None:
    key = username.strip().lower()
    with _rate_lock:
        _fail_tracker.pop(key, None)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class StaffLoginRequest(BaseModel):
    username: str
    password: str


class StaffLoginResponse(BaseModel):
    access_token: str
    role: str


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/staff-login", response_model=StaffLoginResponse)
def staff_login(req: StaffLoginRequest, db: Session = Depends(get_db)):
    username = req.username.strip()
    password = req.password

    # 1. Rate-limit check (before any password verification)
    _check_rate_limit(username)

    # 2. Admin check
    if username.lower() == settings.ADMIN_ID.strip().lower():
        if verify_admin_password(password):
            _clear_fails(username)
            token = create_token(sub=settings.ADMIN_ID, role="admin")
            return StaffLoginResponse(access_token=token, role="admin")
        else:
            _record_fail(username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid ID or password",
            )

    # 3. Built-in auditor check
    if username == settings.AUDITOR_ID:
        if not settings.BUILTIN_AUDITOR_ENABLED:
            _record_fail(username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid ID or password",
            )
        if verify_auditor_password(password):
            _clear_fails(username)
            token = create_token(sub=settings.AUDITOR_ID, role="auditor")
            return StaffLoginResponse(access_token=token, role="auditor")

    # 4. DB auditor lookup by email (case-insensitive)
    auditor: Optional[Auditor] = (
        db.query(Auditor)
        .filter(Auditor.email == username.lower())
        .first()
    )

    if auditor and auditor.password_hash:
        # Verify password FIRST
        try:
            password_correct = bcrypt.checkpw(
                password.encode("utf-8"),
                auditor.password_hash.encode("utf-8")
                if isinstance(auditor.password_hash, str)
                else auditor.password_hash,
            )
        except Exception:
            password_correct = False

        if password_correct:
            # Password is correct — now check status
            if auditor.status != "active":
                # Don't record a fail; password was right, account is disabled
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This account is disabled. Contact the admin.",
                )
            # Issue token with auditor_id claim
            _clear_fails(username)
            token = create_token(
                sub=auditor.email,
                role="auditor",
                extra={"auditor_id": auditor.id},
            )
            # Update last_login_at
            auditor.last_login_at = datetime.utcnow()
            db.commit()
            return StaffLoginResponse(access_token=token, role="auditor")
        else:
            # Wrong password for a known DB auditor
            _record_fail(username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid ID or password",
            )

    # 5. Unknown user or DB auditor with no password set
    _record_fail(username)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid ID or password",
    )
