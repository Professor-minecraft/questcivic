from datetime import datetime
import hashlib
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
import bcrypt

from app.database import get_db
from app.models import Auditor

router = APIRouter(prefix="/auth", tags=["auditor-invite"])


class AuditorInviteInfoResponse(BaseModel):
    name: str
    email: str


class AuditorSetPasswordRequest(BaseModel):
    token: str
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8 or not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError(
                "Password must be at least 8 characters with at least one letter and one digit"
            )
        return v


@router.get(
    "/auditor-invite/{token}",
    response_model=AuditorInviteInfoResponse,
)
def get_auditor_invite(token: str, db: Session = Depends(get_db)):
    t = token.strip() if token else ""
    if not t:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link is invalid or expired",
        )

    token_hash = hashlib.sha256(t.encode("utf-8")).hexdigest()
    auditor = db.query(Auditor).filter(Auditor.invite_token_hash == token_hash).first()

    if not auditor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link is invalid or expired",
        )

    if auditor.invite_expires_at is None or auditor.invite_expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link is invalid or expired",
        )

    # Check if already used
    if auditor.password_hash:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link is invalid or expired",
        )

    return AuditorInviteInfoResponse(
        name=auditor.name,
        email=auditor.email,
    )


@router.post("/auditor-set-password")
def set_auditor_password(
    req: AuditorSetPasswordRequest,
    db: Session = Depends(get_db),
):
    t = req.token.strip() if req.token else ""
    if not t:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link is invalid or expired",
        )

    token_hash = hashlib.sha256(t.encode("utf-8")).hexdigest()
    auditor = db.query(Auditor).filter(Auditor.invite_token_hash == token_hash).first()

    if not auditor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link is invalid or expired",
        )

    if auditor.invite_expires_at is None or auditor.invite_expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link is invalid or expired",
        )

    if auditor.password_hash:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link is invalid or expired",
        )

    # Hash password with bcrypt
    pwd_bytes = req.password.encode("utf-8")
    hashed = bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")

    auditor.password_hash = hashed
    auditor.invite_token_hash = None
    auditor.invite_expires_at = None
    db.commit()

    return {"message": "Password set successfully"}
