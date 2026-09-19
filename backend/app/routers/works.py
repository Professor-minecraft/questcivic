from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Submission, User, Work
from app.schemas import WorkItemResponse, WorksListResponse
from app.security import get_current_user
from app.services.csv_loader import normalize_text

router = APIRouter(prefix="/works", tags=["works"])


@router.get("", response_model=WorksListResponse)
def get_works(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # If the user has no saved location, return 400 with "Location not set"
    if not current_user.state or not current_user.district or not current_user.constituency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Location not set",
        )

    if source is not None:
        if source not in ("LS", "RS"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid source parameter. Must be 'LS' or 'RS'.",
            )

    user_state_norm = normalize_text(current_user.state)
    user_district_norm = normalize_text(current_user.district)
    user_constituency_norm = normalize_text(current_user.constituency)

    # Lok Sabha works match state, district, and constituency
    ls_condition = and_(
        Work.source == "LS",
        Work.state_norm == user_state_norm,
        Work.district_norm == user_district_norm,
        Work.constituency_norm == user_constituency_norm,
    )

    # Rajya Sabha works match state and district
    rs_condition = and_(
        Work.source == "RS",
        Work.state_norm == user_state_norm,
        Work.district_norm == user_district_norm,
    )

    if source == "LS":
        query = db.query(Work).filter(ls_condition)
    elif source == "RS":
        query = db.query(Work).filter(rs_condition)
    else:
        query = db.query(Work).filter(or_(ls_condition, rs_condition))

    # Optional search on description or work_type (case-insensitive)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Work.description.ilike(term),
                Work.work_type.ilike(term),
            )
        )

    total = query.count()

    # Sort by completion_date descending
    works = (
        query.order_by(Work.completion_date.desc().nullslast(), Work.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # Fetch latest submission status for current user for each returned work
    work_ids = [w.id for w in works]
    latest_status_by_work = {}
    if work_ids:
        submissions = (
            db.query(Submission)
            .filter(
                Submission.user_id == current_user.id,
                Submission.work_id.in_(work_ids),
            )
            .order_by(Submission.created_at.desc(), Submission.id.desc())
            .all()
        )
        for sub in submissions:
            if sub.work_id not in latest_status_by_work:
                latest_status_by_work[sub.work_id] = sub.status

    items = [
        WorkItemResponse(
            id=w.id,
            source=w.source,
            work_code=w.work_code,
            work_type=w.work_type,
            description=w.description,
            mp_name=w.mp_name,
            state=w.state,
            district=w.district,
            constituency=w.constituency,
            amount=w.amount,
            completion_date=w.completion_date,
            my_submission_status=latest_status_by_work.get(w.id),
        )
        for w in works
    ]

    return WorksListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
