"""
Admin Review Routes:
- GET /admin/reviews
- GET /admin/auditors/{id}/summary
"""
from datetime import datetime, time, timedelta, timezone
from typing import List, Optional, Union
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Auditor, Complaint, ReviewLog, Submission, User, Work
from app.security import require_admin

router = APIRouter(prefix="/admin", tags=["admin-reviews"])

KOLKATA_TZ = ZoneInfo("Asia/Kolkata")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ReviewAuditor(BaseModel):
    id: Optional[int] = None
    name: str
    email: str
    builtin: bool


class ReviewUser(BaseModel):
    id: int
    name: Optional[str] = None
    email: str


class AdminReviewItem(BaseModel):
    review_id: int
    created_at: datetime
    auditor: ReviewAuditor
    kind: str
    decision: str
    target_id: int
    title: str
    user: ReviewUser
    state: str
    district: str
    constituency: Optional[str] = None
    comment: Optional[str] = None
    submitted_at: datetime
    review_minutes: Union[int, float]


class AdminReviewsListResponse(BaseModel):
    items: List[AdminReviewItem]
    total: int
    page: int
    page_size: int


class PerDayCount(BaseModel):
    date: str
    count: int


class AuditorSummaryResponse(BaseModel):
    reviews_total: int
    photos_approved: int
    photos_rejected: int
    complaints_accepted: int
    complaints_rejected: int
    approval_rate: Optional[float] = None
    avg_review_minutes: Optional[float] = None
    first_review_at: Optional[datetime] = None
    last_review_at: Optional[datetime] = None
    per_day: List[PerDayCount]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_auditor_info(ref: str, db: Session) -> ReviewAuditor:
    if ref.lower() in (settings.AUDITOR_ID.lower(), "builtin"):
        return ReviewAuditor(
            id=None,
            name="Built-in auditor",
            email=settings.AUDITOR_ID,
            builtin=True,
        )

    aud = db.query(Auditor).filter(Auditor.email.ilike(ref)).first()
    if not aud and ref.isdigit():
        aud = db.query(Auditor).filter(Auditor.id == int(ref)).first()

    if aud:
        return ReviewAuditor(
            id=aud.id,
            name=aud.name,
            email=aud.email,
            builtin=False,
        )

    return ReviewAuditor(
        id=None,
        name=ref,
        email=ref,
        builtin=False,
    )


def _calc_review_minutes(submitted_at: datetime, reviewed_at: datetime) -> Union[int, float]:
    delta_secs = max(0.0, (reviewed_at - submitted_at).total_seconds())
    mins = round(delta_secs / 60.0, 1)
    if mins.is_integer():
        return int(mins)
    return mins


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/reviews", response_model=AdminReviewsListResponse)
def get_admin_reviews(
    auditor_id: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    kind: str = Query("all"),
    decision: str = Query("all"),
    range_param: str = Query("all", alias="range"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    valid_kinds = {"all", "submission", "complaint"}
    if kind not in valid_kinds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid kind filter. Allowed: all, submission, complaint.",
        )

    valid_decisions = {"all", "approved", "rejected", "accepted"}
    if decision not in valid_decisions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid decision filter. Allowed: all, approved, rejected, accepted.",
        )

    valid_ranges = {"today", "7d", "30d", "all"}
    if range_param not in valid_ranges:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid range filter. Allowed: today, 7d, 30d, all.",
        )

    query = db.query(ReviewLog)

    # 1. Auditor filter
    if auditor_id and auditor_id.strip():
        aid = auditor_id.strip()
        if aid.lower() == "builtin":
            query = query.filter(
                (ReviewLog.auditor_ref.ilike(settings.AUDITOR_ID))
                | (ReviewLog.auditor_ref.ilike("builtin"))
            )
        elif aid.isdigit():
            aud = db.query(Auditor).filter(Auditor.id == int(aid)).first()
            if aud:
                query = query.filter(
                    (ReviewLog.auditor_ref.ilike(aud.email))
                    | (ReviewLog.auditor_ref == str(aud.id))
                )
            else:
                query = query.filter(ReviewLog.id == -1)
        else:
            query = query.filter(ReviewLog.auditor_ref.ilike(aid))

    # 2. Kind filter
    if kind != "all":
        query = query.filter(ReviewLog.kind == kind)

    # 3. Decision filter
    if decision != "all":
        query = query.filter(ReviewLog.decision == decision)

    # 4. User filter (target user of submission or complaint)
    if user_id is not None:
        user_sub_ids = [
            r[0] for r in db.query(Submission.id).filter(Submission.user_id == user_id).all()
        ]
        user_comp_ids = [
            r[0] for r in db.query(Complaint.id).filter(Complaint.user_id == user_id).all()
        ]
        query = query.filter(
            ((ReviewLog.kind == "submission") & (ReviewLog.target_id.in_(user_sub_ids)))
            | ((ReviewLog.kind == "complaint") & (ReviewLog.target_id.in_(user_comp_ids)))
        )

    # 5. Date range filter (using Asia/Kolkata timezone)
    now_kolkata = datetime.now(KOLKATA_TZ)
    if range_param == "today":
        start_of_today_kol = datetime.combine(now_kolkata.date(), time.min, tzinfo=KOLKATA_TZ)
        start_utc = start_of_today_kol.astimezone(timezone.utc).replace(tzinfo=None)
        query = query.filter(ReviewLog.created_at >= start_utc)
    elif range_param == "7d":
        start_utc = (now_kolkata - timedelta(days=7)).astimezone(timezone.utc).replace(tzinfo=None)
        query = query.filter(ReviewLog.created_at >= start_utc)
    elif range_param == "30d":
        start_utc = (now_kolkata - timedelta(days=30)).astimezone(timezone.utc).replace(tzinfo=None)
        query = query.filter(ReviewLog.created_at >= start_utc)

    # Order newest first
    query = query.order_by(ReviewLog.created_at.desc(), ReviewLog.id.desc())
    total = query.count()
    logs = query.offset((page - 1) * page_size).limit(page_size).all()

    # Pre-fetch referenced targets, works, and users
    sub_ids = [lg.target_id for lg in logs if lg.kind == "submission"]
    comp_ids = [lg.target_id for lg in logs if lg.kind == "complaint"]

    subs = (
        {s.id: s for s in db.query(Submission).filter(Submission.id.in_(sub_ids)).all()}
        if sub_ids
        else {}
    )
    comps = (
        {c.id: c for c in db.query(Complaint).filter(Complaint.id.in_(comp_ids)).all()}
        if comp_ids
        else {}
    )

    work_ids = [s.work_id for s in subs.values()]
    works = (
        {w.id: w for w in db.query(Work).filter(Work.id.in_(work_ids)).all()}
        if work_ids
        else {}
    )

    target_user_ids = [s.user_id for s in subs.values()] + [c.user_id for c in comps.values()]
    users = (
        {u.id: u for u in db.query(User).filter(User.id.in_(target_user_ids)).all()}
        if target_user_ids
        else {}
    )

    items = []
    for lg in logs:
        auditor_info = _resolve_auditor_info(lg.auditor_ref, db)

        if lg.kind == "submission":
            sub = subs.get(lg.target_id)
            work = works.get(sub.work_id) if sub else None
            user = users.get(sub.user_id) if sub else None

            title = work.work_type if work else ""
            user_obj = (
                ReviewUser(id=user.id, name=user.name, email=user.email)
                if user
                else ReviewUser(id=0, name=None, email="unknown")
            )
            state = work.state if work else ""
            district = work.district if work else ""
            constituency = work.constituency if work else None
            comment = sub.reject_reason if (sub and lg.decision == "rejected") else None
            submitted_at = sub.created_at if sub else lg.created_at

        else:  # complaint
            comp = comps.get(lg.target_id)
            user = users.get(comp.user_id) if comp else None

            title = (comp.comment or "")[:80] if comp else ""
            user_obj = (
                ReviewUser(id=user.id, name=user.name, email=user.email)
                if user
                else ReviewUser(id=0, name=None, email="unknown")
            )
            state = comp.state if comp else ""
            district = comp.district if comp else ""
            constituency = comp.constituency if comp else None
            comment = comp.auditor_comment if comp else None
            submitted_at = comp.created_at if comp else lg.created_at

        review_minutes = _calc_review_minutes(submitted_at, lg.created_at)

        items.append(
            AdminReviewItem(
                review_id=lg.id,
                created_at=lg.created_at,
                auditor=auditor_info,
                kind=lg.kind,
                decision=lg.decision,
                target_id=lg.target_id,
                title=title,
                user=user_obj,
                state=state,
                district=district,
                constituency=constituency,
                comment=comment,
                submitted_at=submitted_at,
                review_minutes=review_minutes,
            )
        )

    return AdminReviewsListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/auditors/{id}/summary", response_model=AuditorSummaryResponse)
def get_admin_auditor_summary(
    id: str,
    range_param: str = Query("all", alias="range"),
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    valid_ranges = {"7d", "30d", "all"}
    if range_param not in valid_ranges:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid range filter. Allowed: 7d, 30d, all.",
        )

    is_builtin = id.lower() in ("builtin", "0", settings.AUDITOR_ID.lower())
    if is_builtin:
        auditor_refs = [settings.AUDITOR_ID, "builtin"]
    elif id.isdigit():
        aud = db.query(Auditor).filter(Auditor.id == int(id)).first()
        if not aud:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Auditor not found",
            )
        auditor_refs = [aud.email, str(aud.id)]
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Auditor not found",
        )

    # 1. Filter logs for the requested summary range
    now_kolkata = datetime.now(KOLKATA_TZ)
    query = db.query(ReviewLog).filter(ReviewLog.auditor_ref.in_(auditor_refs))

    if range_param == "7d":
        start_utc = (now_kolkata - timedelta(days=7)).astimezone(timezone.utc).replace(tzinfo=None)
        query = query.filter(ReviewLog.created_at >= start_utc)
    elif range_param == "30d":
        start_utc = (now_kolkata - timedelta(days=30)).astimezone(timezone.utc).replace(tzinfo=None)
        query = query.filter(ReviewLog.created_at >= start_utc)

    filtered_logs = query.order_by(ReviewLog.created_at.asc(), ReviewLog.id.asc()).all()

    reviews_total = len(filtered_logs)
    photos_approved = sum(
        1 for lg in filtered_logs if lg.kind == "submission" and lg.decision == "approved"
    )
    photos_rejected = sum(
        1 for lg in filtered_logs if lg.kind == "submission" and lg.decision == "rejected"
    )
    complaints_accepted = sum(
        1 for lg in filtered_logs if lg.kind == "complaint" and lg.decision == "accepted"
    )
    complaints_rejected = sum(
        1 for lg in filtered_logs if lg.kind == "complaint" and lg.decision == "rejected"
    )

    approval_rate = (
        round((photos_approved + complaints_accepted) / reviews_total, 4)
        if reviews_total > 0
        else None
    )

    first_review_at = filtered_logs[0].created_at if filtered_logs else None
    last_review_at = filtered_logs[-1].created_at if filtered_logs else None

    # Calculate average review minutes
    avg_review_minutes = None
    if reviews_total > 0:
        sub_ids = [lg.target_id for lg in filtered_logs if lg.kind == "submission"]
        comp_ids = [lg.target_id for lg in filtered_logs if lg.kind == "complaint"]
        subs = (
            {s.id: s for s in db.query(Submission).filter(Submission.id.in_(sub_ids)).all()}
            if sub_ids
            else {}
        )
        comps = (
            {c.id: c for c in db.query(Complaint).filter(Complaint.id.in_(comp_ids)).all()}
            if comp_ids
            else {}
        )

        minutes_list = []
        for lg in filtered_logs:
            submitted_at = None
            if lg.kind == "submission" and lg.target_id in subs:
                submitted_at = subs[lg.target_id].created_at
            elif lg.kind == "complaint" and lg.target_id in comps:
                submitted_at = comps[lg.target_id].created_at

            if submitted_at:
                delta_secs = max(0.0, (lg.created_at - submitted_at).total_seconds())
                minutes_list.append(delta_secs / 60.0)

        if minutes_list:
            avg_review_minutes = round(sum(minutes_list) / len(minutes_list), 1)

    # 2. Per-day counts: always the last 30 days in Asia/Kolkata timezone with zeros filled in
    today_kolkata_date = now_kolkata.date()
    days_30 = [today_kolkata_date - timedelta(days=i) for i in range(29, -1, -1)]
    per_day_map = {d.isoformat(): 0 for d in days_30}

    # Fetch logs from start of the 30-day window
    window_start_kol = datetime.combine(days_30[0], time.min, tzinfo=KOLKATA_TZ)
    window_start_utc = window_start_kol.astimezone(timezone.utc).replace(tzinfo=None)

    window_logs = (
        db.query(ReviewLog)
        .filter(
            ReviewLog.auditor_ref.in_(auditor_refs),
            ReviewLog.created_at >= window_start_utc,
        )
        .all()
    )

    for lg in window_logs:
        dt = lg.created_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        d_str = dt.astimezone(KOLKATA_TZ).date().isoformat()
        if d_str in per_day_map:
            per_day_map[d_str] += 1

    per_day = [PerDayCount(date=d.isoformat(), count=per_day_map[d.isoformat()]) for d in days_30]

    return AuditorSummaryResponse(
        reviews_total=reviews_total,
        photos_approved=photos_approved,
        photos_rejected=photos_rejected,
        complaints_accepted=complaints_accepted,
        complaints_rejected=complaints_rejected,
        approval_rate=approval_rate,
        avg_review_minutes=avg_review_minutes,
        first_review_at=first_review_at,
        last_review_at=last_review_at,
        per_day=per_day,
    )
