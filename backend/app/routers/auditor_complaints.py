from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Auditor, Complaint, ReviewLog, User
from app.schemas import (
    AuditorComplaintItem,
    AuditorComplaintsListResponse,
    AuditorComplaintReviewRequest,
    ComplaintResponse,
)
from app.security import require_auditor
from app.services.normalize import normalize_place

router = APIRouter(prefix="/auditor/complaints", tags=["auditor_complaints"])


def _apply_complaint_scope(query, auditor: dict, db: Session):
    """
    If the auditor token has an auditor_id (DB auditor), filter complaints
    to only those whose state_norm and constituency_norm match the auditor's
    assigned location.  Built-in auditor (no auditor_id) sees everything.
    """
    auditor_id = auditor.get("auditor_id")
    if auditor_id is None:
        return query  # built-in: no filter
    auditor_row = db.query(Auditor).filter(Auditor.id == int(auditor_id)).first()
    if not auditor_row:
        return query
    state_norm = normalize_place(auditor_row.state)
    constituency_norm = normalize_place(auditor_row.constituency)
    query = query.filter(
        Complaint.state_norm == state_norm,
        Complaint.constituency_norm == constituency_norm,
    )
    return query


def _complaint_in_scope(complaint: Complaint, auditor: dict, db: Session) -> bool:
    """Return True if the complaint is within the auditor's scope."""
    auditor_id = auditor.get("auditor_id")
    if auditor_id is None:
        return True  # built-in: all in scope
    auditor_row = db.query(Auditor).filter(Auditor.id == int(auditor_id)).first()
    if not auditor_row:
        return True
    return (
        normalize_place(auditor_row.state) == complaint.state_norm
        and normalize_place(auditor_row.constituency) == complaint.constituency_norm
    )


@router.get("", response_model=AuditorComplaintsListResponse)
def get_auditor_complaints(
    status_filter: Optional[str] = Query("pending", alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    auditor: dict = Depends(require_auditor),
    db: Session = Depends(get_db),
):
    valid_statuses = {"pending", "accepted", "rejected", "all"}
    chosen_status = (status_filter or "pending").strip().lower()
    if chosen_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status filter. Allowed values: pending, accepted, rejected, all.",
        )

    query = db.query(Complaint)
    if chosen_status != "all":
        query = query.filter(Complaint.status == chosen_status)

    # Apply constituency scope for DB auditors
    query = _apply_complaint_scope(query, auditor, db)

    query = query.order_by(Complaint.created_at.desc(), Complaint.id.desc())

    total = query.count()
    complaints = query.offset((page - 1) * page_size).limit(page_size).all()

    user_ids = [c.user_id for c in complaints]
    users = (
        {u.id: u.email for u in db.query(User.id, User.email).filter(User.id.in_(user_ids)).all()}
        if user_ids
        else {}
    )

    items = [
        AuditorComplaintItem(
            id=c.id,
            comment=c.comment,
            status=c.status,
            auditor_comment=c.auditor_comment,
            xp_awarded=c.xp_awarded,
            state=c.state,
            district=c.district,
            constituency=c.constituency,
            lat=c.lat,
            lng=c.lng,
            created_at=c.created_at,
            reviewed_at=c.reviewed_at,
            user_email=users.get(c.user_id, c.user.email if c.user else "unknown"),
        )
        for c in complaints
    ]

    return AuditorComplaintsListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{id}/accept", response_model=ComplaintResponse)
def accept_complaint(
    id: int,
    req: AuditorComplaintReviewRequest,
    auditor: dict = Depends(require_auditor),
    db: Session = Depends(get_db),
):
    clean_comment = req.comment.strip()
    if len(clean_comment) < 3 or len(clean_comment) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comment must be between 3 and 500 characters.",
        )

    complaint = db.query(Complaint).filter(Complaint.id == id).first()
    if not complaint or not _complaint_in_scope(complaint, auditor, db):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found",
        )

    if complaint.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Complaint is already {complaint.status}.",
        )

    user = db.query(User).filter(User.id == complaint.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # In ONE database transaction:
    # set status "accepted", save auditor_comment, set reviewed_at,
    # set xp_awarded to XP_PER_COMPLAINT, and add XP_PER_COMPLAINT to users.xp.
    try:
        complaint.status = "accepted"
        complaint.auditor_comment = clean_comment
        complaint.reviewed_at = datetime.utcnow()
        complaint.xp_awarded = settings.XP_PER_COMPLAINT
        user.xp = (user.xp or 0) + settings.XP_PER_COMPLAINT

        review_entry = ReviewLog(
            auditor_ref=str(auditor.get("sub", "")),
            kind="complaint",
            target_id=complaint.id,
            decision="accepted",
            created_at=datetime.utcnow(),
        )
        db.add(review_entry)

        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(complaint)
    return complaint


@router.post("/{id}/reject", response_model=ComplaintResponse)
def reject_complaint(
    id: int,
    req: AuditorComplaintReviewRequest,
    auditor: dict = Depends(require_auditor),
    db: Session = Depends(get_db),
):
    clean_comment = req.comment.strip()
    if len(clean_comment) < 3 or len(clean_comment) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comment must be between 3 and 500 characters.",
        )

    complaint = db.query(Complaint).filter(Complaint.id == id).first()
    if not complaint or not _complaint_in_scope(complaint, auditor, db):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found",
        )

    if complaint.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Complaint is already {complaint.status}.",
        )

    try:
        complaint.status = "rejected"
        complaint.auditor_comment = clean_comment
        complaint.reviewed_at = datetime.utcnow()
        # No XP awarded

        review_entry = ReviewLog(
            auditor_ref=str(auditor.get("sub", "")),
            kind="complaint",
            target_id=complaint.id,
            decision="rejected",
            created_at=datetime.utcnow(),
        )
        db.add(review_entry)

        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(complaint)
    return complaint
