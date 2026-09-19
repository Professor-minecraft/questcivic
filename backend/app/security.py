from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

ALGORITHM = "HS256"
security_scheme = HTTPBearer(auto_error=False)

# In-memory bcrypt hashes created at startup
_auditor_password_hash: Optional[bytes] = None
_admin_password_hash: Optional[bytes] = None


def init_auditor_credentials() -> None:
    global _auditor_password_hash
    if settings.AUDITOR_PASSWORD:
        pwd_bytes = settings.AUDITOR_PASSWORD.encode("utf-8")
        _auditor_password_hash = bcrypt.hashpw(pwd_bytes, bcrypt.gensalt())


def init_admin_credentials() -> None:
    global _admin_password_hash
    if settings.ADMIN_PASSWORD:
        pwd_bytes = settings.ADMIN_PASSWORD.encode("utf-8")
        _admin_password_hash = bcrypt.hashpw(pwd_bytes, bcrypt.gensalt())


def verify_admin_password(password: str) -> bool:
    global _admin_password_hash
    if _admin_password_hash is None:
        init_admin_credentials()
    if not _admin_password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), _admin_password_hash)
    except Exception:
        return False


def verify_auditor_password(password: str) -> bool:
    global _auditor_password_hash
    if _auditor_password_hash is None:
        init_auditor_credentials()
    if not _auditor_password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), _auditor_password_hash)
    except Exception:
        return False


def create_token(sub: str, role: str, extra: Optional[dict] = None) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": str(sub),
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=24),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def get_token_payload(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> dict:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    payload: dict = Depends(get_token_payload),
    db: Session = Depends(get_db),
) -> User:
    role = payload.get("role")
    if role != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: User access required",
        )
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    try:
        user_id = int(sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if user.password_changed_at:
        iat = payload.get("iat")
        if iat is not None:
            token_iat = iat if isinstance(iat, (int, float)) else iat.replace(tzinfo=timezone.utc).timestamp()
            pwd_changed_dt = user.password_changed_at
            pwd_changed_ts = (
                pwd_changed_dt.replace(tzinfo=timezone.utc).timestamp()
                if pwd_changed_dt.tzinfo is None
                else pwd_changed_dt.timestamp()
            )
            if token_iat < pwd_changed_ts:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token invalidated by password change. Please log in again.",
                )

    return user


def require_auditor(payload: dict = Depends(get_token_payload), db: Session = Depends(get_db)) -> dict:
    role = payload.get("role")
    if role != "auditor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Auditor access required",
        )
    # If this is a DB-backed auditor (has auditor_id claim), verify it is still active
    auditor_id = payload.get("auditor_id")
    if auditor_id is not None:
        from app.models import Auditor
        auditor_row = db.query(Auditor).filter(Auditor.id == int(auditor_id)).first()
        if not auditor_row or auditor_row.status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account is disabled. Contact the admin.",
            )
    return payload


def require_admin(payload: dict = Depends(get_token_payload)) -> dict:
    role = payload.get("role")
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin access required",
        )
    return payload
