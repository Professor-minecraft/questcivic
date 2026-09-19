from typing import Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import get_token_payload


class AuthUserOrAuditor:
    def __init__(self, role: str, user: Optional[User] = None, auditor_payload: Optional[dict] = None):
        self.role = role
        self.user = user
        self.is_auditor = role == "auditor"
        self.is_user = role == "user"
        self.auditor_payload = auditor_payload  # full JWT payload when is_auditor=True


def get_current_user_or_auditor(
    payload: dict = Depends(get_token_payload),
    db: Session = Depends(get_db),
) -> AuthUserOrAuditor:
    role = payload.get("role")
    if role == "auditor":
        return AuthUserOrAuditor(role="auditor", auditor_payload=payload)
    elif role == "user":
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
        return AuthUserOrAuditor(role="user", user=user)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid role",
        )
