from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Submission, User, Work, XPLog
from app.schemas import (
    UserStatsResponse,
    UserSubmissionItem,
    UserSubmissionsResponse,
)
from app.security import get_current_user

router = APIRouter(prefix="/me", tags=["profile"])


@router.get("/stats", response_model=UserStatsResponse)
def get_user_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    approved_count = (
        db.query(Submission)
        .filter(
            Submission.user_id == current_user.id,
            Submission.status == "approved",
        )
        .count()
    )
    rejected_count = (
        db.query(Submission)
        .filter(
            Submission.user_id == current_user.id,
            Submission.status == "rejected",
        )
        .count()
    )
    pending_count = (
        db.query(Submission)
        .filter(
            Submission.user_id == current_user.id,
            Submission.status == "pending",
        )
        .count()
    )

    return UserStatsResponse(
        xp=current_user.xp or 0,
        approved=approved_count,
        rejected=rejected_count,
        pending=pending_count,
    )


@router.get("/submissions", response_model=UserSubmissionsResponse)
def get_user_submissions(
    status_filter: Optional[str] = Query("all", alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    valid_statuses = ("all", "approved", "rejected")
    chosen_status = (status_filter or "all").strip().lower()
    if chosen_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status parameter. Must be 'all', 'approved', or 'rejected'.",
        )

    # Filter only current user's submissions
    query = db.query(Submission).filter(Submission.user_id == current_user.id)

    # status "all" means approved and rejected only (pending is not included)
    if chosen_status == "all":
        query = query.filter(Submission.status.in_(["approved", "rejected"]))
    else:
        query = query.filter(Submission.status == chosen_status)

    # Sort by reviewed_at descending
    query = query.order_by(Submission.reviewed_at.desc().nullslast(), Submission.id.desc())

    total = query.count()
    submissions = query.offset((page - 1) * page_size).limit(page_size).all()

    # Pre-fetch works and xp_logs for the page to optimize queries
    sub_ids = [s.id for s in submissions]
    work_ids = [s.work_id for s in submissions]

    works_by_id = {}
    if work_ids:
        works = db.query(Work).filter(Work.id.in_(work_ids)).all()
        works_by_id = {w.id: w for w in works}

    xp_by_sub = {}
    if sub_ids:
        xp_logs = db.query(XPLog).filter(XPLog.submission_id.in_(sub_ids)).all()
        for x in xp_logs:
            xp_by_sub[x.submission_id] = x.points

    items = []
    for sub in submissions:
        work = works_by_id.get(sub.work_id)
        items.append(
            UserSubmissionItem(
                submission_id=sub.id,
                work_id=sub.work_id,
                source=work.source if work else "",
                work_type=work.work_type if work else "",
                description=work.description if work else "",
                mp_name=work.mp_name if work else None,
                state=work.state if work else "",
                district=work.district if work else "",
                constituency=work.constituency if work else None,
                amount=work.amount if work else None,
                completion_date=work.completion_date if work else None,
                status=sub.status,
                reject_reason=sub.reject_reason,
                submitted_at=sub.created_at,
                reviewed_at=sub.reviewed_at,
                xp_earned=xp_by_sub.get(sub.id, 0),
            )
        )

    return UserSubmissionsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
