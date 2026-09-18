from datetime import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Submission, User, Work, XPLog
from app.schemas import (
    AuditorSubmissionItem,
    AuditorSubmissionWorkDetails,
    RejectSubmissionRequest,
    SubmissionResponse,
)
from app.security import require_auditor

router = APIRouter(prefix="/auditor", tags=["auditor"])


@router.get("/submissions", response_model=List[AuditorSubmissionItem])
def get_submissions(
    status: Optional[str] = Query("pending"),
    auditor: dict = Depends(require_auditor),
    db: Session = Depends(get_db),
):
    query = db.query(Submission)
    if status and status.strip():
        query = query.filter(Submission.status == status.strip().lower())

    submissions = query.order_by(Submission.created_at.desc(), Submission.id.desc()).all()

    result = []
    for sub in submissions:
        work = db.query(Work).filter(Work.id == sub.work_id).first()
        user = db.query(User).filter(User.id == sub.user_id).first()
        if not work or not user:
            continue

        work_details = AuditorSubmissionWorkDetails(
            id=work.id,
            source=work.source,
            work_code=work.work_code,
            work_type=work.work_type,
            description=work.description,
            mp_name=work.mp_name,
            state=work.state,
            district=work.district,
            constituency=work.constituency,
        )

        result.append(
            AuditorSubmissionItem(
                id=sub.id,
                user_id=sub.user_id,
                user_email=user.email,
                work_id=sub.work_id,
                work=work_details,
                image_path=sub.image_path,
                status=sub.status,
                lat=sub.lat,
                lng=sub.lng,
                reject_reason=sub.reject_reason,
                created_at=sub.created_at,
                reviewed_at=sub.reviewed_at,
            )
        )

    return result


@router.get("/submissions/{id}/image")
def get_submission_image(
    id: int,
    auditor: dict = Depends(require_auditor),
    db: Session = Depends(get_db),
):
    sub = db.query(Submission).filter(Submission.id == id).first()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found",
        )

    file_path = Path(__file__).resolve().parent.parent.parent / sub.image_path
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file not found",
        )

    return FileResponse(file_path)


@router.post("/submissions/{id}/approve", response_model=SubmissionResponse)
def approve_submission(
    id: int,
    auditor: dict = Depends(require_auditor),
    db: Session = Depends(get_db),
):
    sub = db.query(Submission).filter(Submission.id == id).first()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found",
        )

    if sub.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Submission is already {sub.status}.",
        )

    # In a single database transaction:
    # 1. Update submission status to approved and reviewed_at
    sub.status = "approved"
    sub.reviewed_at = datetime.utcnow()

    # 2. Add XP_PER_APPROVAL to user
    user = db.query(User).filter(User.id == sub.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    user.xp += settings.XP_PER_APPROVAL

    # 3. Insert xp_log row
    xp_entry = XPLog(
        user_id=user.id,
        submission_id=sub.id,
        points=settings.XP_PER_APPROVAL,
        created_at=datetime.utcnow(),
    )
    db.add(xp_entry)

    db.commit()
    db.refresh(sub)
    return sub


@router.post("/submissions/{id}/reject", response_model=SubmissionResponse)
def reject_submission(
    id: int,
    req: RejectSubmissionRequest,
    auditor: dict = Depends(require_auditor),
    db: Session = Depends(get_db),
):
    sub = db.query(Submission).filter(Submission.id == id).first()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found",
        )

    if sub.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Submission is already {sub.status}.",
        )

    sub.status = "rejected"
    sub.reject_reason = req.reason.strip()
    sub.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(sub)
    return sub
