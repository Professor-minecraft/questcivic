"""
GET /auditor/me

Returns the authenticated auditor's profile.
- DB auditor (has auditor_id claim): returns data from the auditors table, scope = "constituency"
- Built-in auditor (no auditor_id claim): returns data from settings, scope = "all"
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Auditor
from app.security import require_auditor

router = APIRouter(prefix="/auditor", tags=["auditor"])


class AuditorMeResponse(BaseModel):
    name: str
    email: str
    state: Optional[str]
    district: Optional[str]
    constituency: Optional[str]
    builtin: bool
    scope: str  # "constituency" | "all"


@router.get("/me", response_model=AuditorMeResponse)
def get_auditor_me(
    auditor: dict = Depends(require_auditor),
    db: Session = Depends(get_db),
):
    auditor_id = auditor.get("auditor_id")

    if auditor_id is None:
        # Built-in auditor
        return AuditorMeResponse(
            name="Built-in auditor",
            email=settings.AUDITOR_ID,
            state=None,
            district=None,
            constituency=None,
            builtin=True,
            scope="all",
        )

    # DB auditor
    auditor_row = db.query(Auditor).filter(Auditor.id == int(auditor_id)).first()
    if not auditor_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Auditor not found",
        )

    return AuditorMeResponse(
        name=auditor_row.name,
        email=auditor_row.email,
        state=auditor_row.state,
        district=auditor_row.district,
        constituency=auditor_row.constituency,
        builtin=False,
        scope="constituency",
    )
