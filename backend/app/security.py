from datetime import datetime, timedelta
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

# In-memory bcrypt hash of auditor password (created on startup)
_auditor_password_hash: Optional[bytes] = None


def init_auditor_credentials() -> None:
    global _auditor_password_hash
    if settings.AUDITOR_PASSWORD:
        pwd_bytes = settings.AUDITOR_PASSWORD.encode("utf-8")
        _auditor_password_hash = bcrypt.hashpw(pwd_bytes, bcrypt.gensalt())


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


def create_token(sub: str, role: str) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": str(sub),
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=24),
    }
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
    return user


def require_auditor(payload: dict = Depends(get_token_payload)) -> dict:
    role = payload.get("role")
    if role != "auditor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Auditor access required",
        )
    return payload
