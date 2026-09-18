from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import HTTPException, status
import pyotp

# In-memory stores for rate limiting and temporary secrets
_otp_requests: Dict[str, List[datetime]] = {}
_wrong_attempts: Dict[str, int] = {}
_blocked_until: Dict[str, datetime] = {}
_pending_secrets: Dict[str, str] = {}


def get_or_create_pending_secret(email: str, existing_secret: Optional[str] = None) -> str:
    normalized_email = email.strip().lower()
    if existing_secret:
        return existing_secret
    if normalized_email not in _pending_secrets:
        _pending_secrets[normalized_email] = pyotp.random_base32()
    return _pending_secrets[normalized_email]
def get_pending_secret(email: str) -> Optional[str]:
    return _pending_secrets.get(email.strip().lower())

def check_can_request_otp(email: str) -> None:
    normalized_email = email.strip().lower()
    now = datetime.utcnow()

    # Check if currently blocked
    blocked = _blocked_until.get(normalized_email)
    if blocked and now < blocked:
        remaining_seconds = int((blocked - now).total_seconds())
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many attempts. Account is temporarily blocked for {remaining_seconds} more seconds.",
        )

    # Clean up requests older than 1 hour (3600 seconds)
    one_hour_ago = now - timedelta(hours=1)
    reqs = [t for t in _otp_requests.get(normalized_email, []) if t > one_hour_ago]
    _otp_requests[normalized_email] = reqs

    if len(reqs) >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests. Maximum 5 requests allowed per hour.",
        )

    # Record this request
    _otp_requests[normalized_email].append(now)


def generate_otp_code(secret: str) -> str:
    totp = pyotp.TOTP(secret, digits=6, interval=300)
    return totp.now()


def verify_otp_code(email: str, secret: str, code: str) -> bool:
    normalized_email = email.strip().lower()
    now = datetime.utcnow()

    # Check if blocked
    blocked = _blocked_until.get(normalized_email)
    if blocked and now < blocked:
        remaining_seconds = int((blocked - now).total_seconds())
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Blocked for {remaining_seconds} more seconds.",
        )

    totp = pyotp.TOTP(secret, digits=6, interval=300)
    # Check valid_window=0 as specified in PRD, with fallback to valid_window=1 if boundary just rolled over
    is_valid = totp.verify(code.strip(), valid_window=0) or totp.verify(code.strip(), valid_window=1)

    if not is_valid:
        # Increment failed attempts
        current_attempts = _wrong_attempts.get(normalized_email, 0) + 1
        _wrong_attempts[normalized_email] = current_attempts

        if current_attempts >= 5:
            # Block for 15 minutes
            _blocked_until[normalized_email] = now + timedelta(minutes=15)
            _wrong_attempts[normalized_email] = 0
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed OTP attempts. You have been blocked for 15 minutes.",
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP.",
        )

    # Reset failure tracking on success
    _wrong_attempts.pop(normalized_email, None)
    _blocked_until.pop(normalized_email, None)
    _pending_secrets.pop(normalized_email, None)
    return True
