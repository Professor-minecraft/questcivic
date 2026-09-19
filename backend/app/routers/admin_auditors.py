from datetime import date, datetime, timedelta
import hashlib
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Auditor, Work
from app.schemas import LocationOptionsResponse
from app.security import require_admin
from app.services.invite_email import send_invite_email

router = APIRouter(prefix="/admin", tags=["admin-auditors"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CreateAuditorRequest(BaseModel):
    name: str
    dob: date
    email: str
    state: str
    district: str
    constituency: Optional[str] = None
    status: str = "active"

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        s = v.strip()
        if len(s) < 2 or len(s) > 100:
            raise ValueError("Name must be between 2 and 100 characters")
        return s

    @field_validator("dob")
    @classmethod
    def validate_dob(cls, v: date) -> date:
        today = date.today()
        if v > today:
            raise ValueError("Date of birth cannot be in the future")
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        if age < 18:
            raise ValueError("Auditor must be at least 18 years old")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        s = v.strip().lower()
        allowed_suffix = f"@{settings.ALLOWED_EMAIL_DOMAIN.lower()}"
        if not s.endswith(allowed_suffix):
            raise ValueError(f"Email must end with @{settings.ALLOWED_EMAIL_DOMAIN}")
        local_part = s[: -len(allowed_suffix)]
        if not local_part or "@" in local_part:
            raise ValueError("Invalid email address")
        return s

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        s = v.strip().lower()
        if s not in ("active", "disabled"):
            raise ValueError("Status must be 'active' or 'disabled'")
        return s


class CreateAuditorResponse(BaseModel):
    id: int
    name: str
    email: str
    state: str
    district: str
    constituency: Optional[str] = None
    status: str
    email_sent: bool


class UpdateAuditorStatusRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        s = v.strip().lower()
        if s not in ("active", "disabled"):
            raise ValueError("Status must be 'active' or 'disabled'")
        return s


class AuditorStatusResponse(BaseModel):
    id: int
    name: str
    email: str
    state: str
    district: str
    constituency: Optional[str] = None
    status: str


class ResendInviteResponse(BaseModel):
    id: int
    email: str
    email_sent: bool
    message: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/auditors",
    response_model=CreateAuditorResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_auditor(
    req: CreateAuditorRequest,
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    email = req.email.strip().lower()

    # Check for duplicate email
    existing = db.query(Auditor).filter(Auditor.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Auditor with this email already exists",
        )

    # Generate invite token and SHA-256 hash
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = datetime.utcnow() + timedelta(hours=settings.INVITE_EXPIRE_HOURS)

    auditor = Auditor(
        name=req.name.strip(),
        dob=req.dob,
        email=email,
        state=req.state.strip(),
        district=req.district.strip(),
        constituency=req.constituency.strip() if req.constituency else None,
        status=req.status,
        password_hash=None,
        invite_token_hash=token_hash,
        invite_expires_at=expires_at,
    )
    db.add(auditor)
    db.commit()
    db.refresh(auditor)

    # Send invite email
    email_sent = send_invite_email(auditor.email, token)

    return CreateAuditorResponse(
        id=auditor.id,
        name=auditor.name,
        email=auditor.email,
        state=auditor.state,
        district=auditor.district,
        constituency=auditor.constituency,
        status=auditor.status,
        email_sent=email_sent,
    )


@router.patch("/auditors/{id}/status", response_model=AuditorStatusResponse)
def update_auditor_status(
    id: int,
    req: UpdateAuditorStatusRequest,
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    auditor = db.query(Auditor).filter(Auditor.id == id).first()
    if not auditor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Auditor not found",
        )

    auditor.status = req.status
    db.commit()
    db.refresh(auditor)

    return AuditorStatusResponse(
        id=auditor.id,
        name=auditor.name,
        email=auditor.email,
        state=auditor.state,
        district=auditor.district,
        constituency=auditor.constituency,
        status=auditor.status,
    )


@router.post("/auditors/{id}/resend-invite", response_model=ResendInviteResponse)
def resend_auditor_invite(
    id: int,
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    auditor = db.query(Auditor).filter(Auditor.id == id).first()
    if not auditor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Auditor not found",
        )

    # Only if the auditor has no password yet (otherwise 409)
    if auditor.password_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Auditor has already set a password",
        )

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = datetime.utcnow() + timedelta(hours=settings.INVITE_EXPIRE_HOURS)

    auditor.invite_token_hash = token_hash
    auditor.invite_expires_at = expires_at
    db.commit()
    db.refresh(auditor)

    email_sent = send_invite_email(auditor.email, token)

    return ResendInviteResponse(
        id=auditor.id,
        email=auditor.email,
        email_sent=email_sent,
        message="Invite resent successfully",
    )


@router.get("/location/options", response_model=LocationOptionsResponse)
def get_admin_location_options(
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    states = sorted([
        s[0]
        for s in db.query(Work.state).distinct().all()
        if s[0]
    ])

    districts = []
    if state:
        districts = sorted([
            d[0]
            for d in db.query(Work.district)
            .filter(Work.state == state)
            .distinct()
            .all()
            if d[0]
        ])

    constituencies = []
    if state and district:
        constituencies = sorted([
            c[0]
            for c in db.query(Work.constituency)
            .filter(
                Work.source == "LS",
                Work.state == state,
                Work.district == district,
                Work.constituency.isnot(None),
                Work.constituency != "",
            )
            .distinct()
            .all()
            if c[0]
        ])

    return LocationOptionsResponse(
        states=states,
        districts=districts,
        constituencies=constituencies,
    )
