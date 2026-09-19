from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Auditor, Complaint, ReviewLog, Submission, User, Work
from app.security import require_admin
from app.services.storage import get_storage

router = APIRouter(prefix="/admin", tags=["admin-views"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ReviewedBy(BaseModel):
    name: str
    email: str
    builtin: bool


class AdminUserItem(BaseModel):
    id: int
    email: str
    name: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    constituency: Optional[str] = None
    xp: int
    created_at: datetime
    photos_approved: int
    photos_rejected: int
    photos_pending: int
    complaints_total: int
    complaints_accepted: int
    complaints_rejected: int = 0
    complaints_pending: int = 0


class AdminUsersListResponse(BaseModel):
    items: List[AdminUserItem]
    total: int
    page: int
    page_size: int


class AdminSubmissionWorkDetails(BaseModel):
    work_type: str
    description: str
    mp_name: Optional[str] = None
    state: str
    district: str
    constituency: Optional[str] = None


class AdminSubmissionItem(BaseModel):
    submission_id: int
    id: int
    user_id: int
    user_email: str
    user_name: Optional[str] = None
    reviewed_by: Optional[ReviewedBy] = None
    work: AdminSubmissionWorkDetails
    work_type: str
    description: str
    mp_name: Optional[str] = None
    state: str
    district: str
    constituency: Optional[str] = None
    status: str
    reject_reason: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class AdminSubmissionsListResponse(BaseModel):
    items: List[AdminSubmissionItem]
    total: int
    page: int
    page_size: int


class AdminComplaintItem(BaseModel):
    id: int
    user_id: int
    user_email: str
    user_name: Optional[str] = None
    reviewed_by: Optional[ReviewedBy] = None
    comment: str
    status: str
    auditor_comment: Optional[str] = None
    xp_awarded: int
    state: str
    district: str
    constituency: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None


class AdminComplaintsListResponse(BaseModel):
    items: List[AdminComplaintItem]
    total: int
    page: int
    page_size: int


class AdminAuditorItem(BaseModel):
    id: Optional[int] = None
    name: str
    dob: Optional[date] = None
    email: str
    state: Optional[str] = None
    district: Optional[str] = None
    constituency: Optional[str] = None
    status: str
    password_set: bool
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    builtin: bool
    reviews_total: int
    photos_approved: int
    photos_rejected: int
    complaints_accepted: int
    complaints_rejected: int


class AdminAuditorsListResponse(BaseModel):
    items: List[AdminAuditorItem]
    total: int
    page: int
    page_size: int


class ReviewLogEntry(BaseModel):
    kind: str
    target_id: int
    decision: str
    created_at: datetime


class AdminAuditorDetailResponse(AdminAuditorItem):
    review_logs: List[ReviewLogEntry] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_user_counts(db: Session, user_id: int) -> dict:
    photos_approved = (
        db.query(Submission)
        .filter(Submission.user_id == user_id, Submission.status == "approved")
        .count()
    )
    photos_rejected = (
        db.query(Submission)
        .filter(Submission.user_id == user_id, Submission.status == "rejected")
        .count()
    )
    photos_pending = (
        db.query(Submission)
        .filter(Submission.user_id == user_id, Submission.status == "pending")
        .count()
    )
    complaints_total = (
        db.query(Complaint)
        .filter(Complaint.user_id == user_id)
        .count()
    )
    complaints_accepted = (
        db.query(Complaint)
        .filter(Complaint.user_id == user_id, Complaint.status == "accepted")
        .count()
    )
    complaints_rejected = (
        db.query(Complaint)
        .filter(Complaint.user_id == user_id, Complaint.status == "rejected")
        .count()
    )
    complaints_pending = (
        db.query(Complaint)
        .filter(Complaint.user_id == user_id, Complaint.status == "pending")
        .count()
    )
    return {
        "photos_approved": photos_approved,
        "photos_rejected": photos_rejected,
        "photos_pending": photos_pending,
        "complaints_total": complaints_total,
        "complaints_accepted": complaints_accepted,
        "complaints_rejected": complaints_rejected,
        "complaints_pending": complaints_pending,
    }


def _get_reviewed_by(db: Session, kind: str, target_id: int, item_status: str) -> Optional[ReviewedBy]:
    if item_status == "pending":
        return None
    latest_log = (
        db.query(ReviewLog)
        .filter(ReviewLog.kind == kind, ReviewLog.target_id == target_id)
        .order_by(ReviewLog.created_at.desc(), ReviewLog.id.desc())
        .first()
    )
    if not latest_log:
        return None

    ref = latest_log.auditor_ref
    if ref.lower() in (settings.AUDITOR_ID.lower(), "builtin"):
        return ReviewedBy(
            name="Built-in auditor",
            email=settings.AUDITOR_ID,
            builtin=True,
        )

    aud = db.query(Auditor).filter(Auditor.email.ilike(ref)).first()
    if not aud and ref.isdigit():
        aud = db.query(Auditor).filter(Auditor.id == int(ref)).first()

    if aud:
        return ReviewedBy(
            name=aud.name,
            email=aud.email,
            builtin=False,
        )

    return ReviewedBy(
        name=ref,
        email=ref,
        builtin=False,
    )


def _get_auditor_review_counts(db: Session, auditor_ref: str) -> dict:
    reviews_total = (
        db.query(ReviewLog)
        .filter(ReviewLog.auditor_ref == auditor_ref)
        .count()
    )
    photos_approved = (
        db.query(ReviewLog)
        .filter(
            ReviewLog.auditor_ref == auditor_ref,
            ReviewLog.kind == "submission",
            ReviewLog.decision == "approved",
        )
        .count()
    )
    photos_rejected = (
        db.query(ReviewLog)
        .filter(
            ReviewLog.auditor_ref == auditor_ref,
            ReviewLog.kind == "submission",
            ReviewLog.decision == "rejected",
        )
        .count()
    )
    complaints_accepted = (
        db.query(ReviewLog)
        .filter(
            ReviewLog.auditor_ref == auditor_ref,
            ReviewLog.kind == "complaint",
            ReviewLog.decision == "accepted",
        )
        .count()
    )
    complaints_rejected = (
        db.query(ReviewLog)
        .filter(
            ReviewLog.auditor_ref == auditor_ref,
            ReviewLog.kind == "complaint",
            ReviewLog.decision == "rejected",
        )
        .count()
    )
    return {
        "reviews_total": reviews_total,
        "photos_approved": photos_approved,
        "photos_rejected": photos_rejected,
        "complaints_accepted": complaints_accepted,
        "complaints_rejected": complaints_rejected,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

# 1) GET /admin/users?search=
@router.get("/users", response_model=AdminUsersListResponse)
def get_admin_users(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if search and search.strip():
        s = f"%{search.strip()}%"
        query = query.filter(
            User.email.ilike(s)
            | User.state.ilike(s)
            | User.district.ilike(s)
            | User.constituency.ilike(s)
        )

    query = query.order_by(User.created_at.desc(), User.id.desc())
    total = query.count()
    users = query.offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for u in users:
        counts = _get_user_counts(db, u.id)
        items.append(
            AdminUserItem(
                id=u.id,
                email=u.email,
                name=u.name,
                state=u.state,
                district=u.district,
                constituency=u.constituency,
                xp=u.xp,
                created_at=u.created_at,
                photos_approved=counts["photos_approved"],
                photos_rejected=counts["photos_rejected"],
                photos_pending=counts["photos_pending"],
                complaints_total=counts["complaints_total"],
                complaints_accepted=counts["complaints_accepted"],
                complaints_rejected=counts["complaints_rejected"],
                complaints_pending=counts["complaints_pending"],
            )
        )

    return AdminUsersListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# 2) GET /admin/users/{id}
@router.get("/users/{id}", response_model=AdminUserItem)
def get_admin_user_detail(
    id: int,
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    u = db.query(User).filter(User.id == id).first()
    if not u:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    counts = _get_user_counts(db, u.id)
    return AdminUserItem(
        id=u.id,
        email=u.email,
        name=u.name,
        state=u.state,
        district=u.district,
        constituency=u.constituency,
        xp=u.xp,
        created_at=u.created_at,
        photos_approved=counts["photos_approved"],
        photos_rejected=counts["photos_rejected"],
        photos_pending=counts["photos_pending"],
        complaints_total=counts["complaints_total"],
        complaints_accepted=counts["complaints_accepted"],
        complaints_rejected=counts["complaints_rejected"],
        complaints_pending=counts["complaints_pending"],
    )


# 3) GET /admin/submissions?status=all|pending|approved|rejected&user_id=
@router.get("/submissions", response_model=AdminSubmissionsListResponse)
def get_admin_submissions(
    status_filter: Optional[str] = Query("all", alias="status"),
    user_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    valid_statuses = {"all", "pending", "approved", "rejected"}
    chosen_status = (status_filter or "all").strip().lower()
    if chosen_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status filter. Allowed values: all, pending, approved, rejected.",
        )

    query = db.query(Submission)
    if chosen_status != "all":
        query = query.filter(Submission.status == chosen_status)
    if user_id is not None:
        query = query.filter(Submission.user_id == user_id)

    query = query.order_by(Submission.created_at.desc(), Submission.id.desc())
    total = query.count()
    submissions = query.offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for sub in submissions:
        work = db.query(Work).filter(Work.id == sub.work_id).first()
        user = db.query(User).filter(User.id == sub.user_id).first()
        if not work or not user:
            continue

        work_details = AdminSubmissionWorkDetails(
            work_type=work.work_type,
            description=work.description,
            mp_name=work.mp_name,
            state=work.state,
            district=work.district,
            constituency=work.constituency,
        )

        items.append(
            AdminSubmissionItem(
                submission_id=sub.id,
                id=sub.id,
                user_id=sub.user_id,
                user_email=user.email,
                user_name=user.name,
                reviewed_by=_get_reviewed_by(db, "submission", sub.id, sub.status),
                work=work_details,
                work_type=work.work_type,
                description=work.description,
                mp_name=work.mp_name,
                state=work.state,
                district=work.district,
                constituency=work.constituency,
                status=sub.status,
                reject_reason=sub.reject_reason,
                created_at=sub.created_at,
                reviewed_at=sub.reviewed_at,
                lat=sub.lat,
                lng=sub.lng,
            )
        )

    return AdminSubmissionsListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# 4) GET /admin/submissions/{id}/image
@router.get("/submissions/{id}/image")
def get_admin_submission_image(
    id: int,
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    sub = db.query(Submission).filter(Submission.id == id).first()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found",
        )

    storage = get_storage()
    return storage.get_file_response(sub.image_path)


# 5) GET /admin/complaints?status=all|pending|accepted|rejected&user_id=
@router.get("/complaints", response_model=AdminComplaintsListResponse)
def get_admin_complaints(
    status_filter: Optional[str] = Query("all", alias="status"),
    user_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    valid_statuses = {"all", "pending", "accepted", "rejected"}
    chosen_status = (status_filter or "all").strip().lower()
    if chosen_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status filter. Allowed values: all, pending, accepted, rejected.",
        )

    query = db.query(Complaint)
    if chosen_status != "all":
        query = query.filter(Complaint.status == chosen_status)
    if user_id is not None:
        query = query.filter(Complaint.user_id == user_id)

    query = query.order_by(Complaint.created_at.desc(), Complaint.id.desc())
    total = query.count()
    complaints = query.offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for c in complaints:
        user = db.query(User).filter(User.id == c.user_id).first()
        user_email = user.email if user else "unknown"

        items.append(
            AdminComplaintItem(
                id=c.id,
                user_id=c.user_id,
                user_email=user_email,
                user_name=user.name if user else None,
                reviewed_by=_get_reviewed_by(db, "complaint", c.id, c.status),
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
            )
        )

    return AdminComplaintsListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# 6) GET /admin/complaints/{id}/image
@router.get("/complaints/{id}/image")
def get_admin_complaint_image(
    id: int,
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    complaint = db.query(Complaint).filter(Complaint.id == id).first()
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found",
        )

    storage = get_storage()
    return storage.get_file_response(complaint.image_path)


# 7) GET /admin/auditors
@router.get("/auditors", response_model=AdminAuditorsListResponse)
def get_admin_auditors(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    # 1. Built-in auditor
    builtin_ref = settings.AUDITOR_ID
    builtin_counts = _get_auditor_review_counts(db, builtin_ref)
    builtin_item = AdminAuditorItem(
        id=None,
        name="Built-in auditor",
        dob=None,
        email=settings.AUDITOR_ID,
        state=None,
        district=None,
        constituency=None,
        status="active",
        password_set=True,
        created_at=None,
        last_login_at=None,
        builtin=True,
        reviews_total=builtin_counts["reviews_total"],
        photos_approved=builtin_counts["photos_approved"],
        photos_rejected=builtin_counts["photos_rejected"],
        complaints_accepted=builtin_counts["complaints_accepted"],
        complaints_rejected=builtin_counts["complaints_rejected"],
    )

    # 2. Database auditors
    db_auditors = (
        db.query(Auditor)
        .order_by(Auditor.created_at.desc(), Auditor.id.desc())
        .all()
    )

    all_items = [builtin_item]
    for a in db_auditors:
        ref = a.email
        counts = _get_auditor_review_counts(db, ref)
        all_items.append(
            AdminAuditorItem(
                id=a.id,
                name=a.name,
                dob=a.dob,
                email=a.email,
                state=a.state,
                district=a.district,
                constituency=a.constituency,
                status=a.status,
                password_set=bool(a.password_hash),
                created_at=a.created_at,
                last_login_at=a.last_login_at,
                builtin=False,
                reviews_total=counts["reviews_total"],
                photos_approved=counts["photos_approved"],
                photos_rejected=counts["photos_rejected"],
                complaints_accepted=counts["complaints_accepted"],
                complaints_rejected=counts["complaints_rejected"],
            )
        )

    total = len(all_items)
    paginated = all_items[(page - 1) * page_size : page * page_size]

    return AdminAuditorsListResponse(
        items=paginated,
        total=total,
        page=page,
        page_size=page_size,
    )


# 8) GET /admin/auditors/{id}
@router.get("/auditors/{id}", response_model=AdminAuditorDetailResponse)
def get_admin_auditor_detail(
    id: Union[int, str],
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    # Handle built-in auditor if id == "builtin" or id == "0"
    if str(id).lower() in ("builtin", "0"):
        builtin_ref = settings.AUDITOR_ID
        builtin_counts = _get_auditor_review_counts(db, builtin_ref)
        logs = (
            db.query(ReviewLog)
            .filter(ReviewLog.auditor_ref == builtin_ref)
            .order_by(ReviewLog.created_at.desc(), ReviewLog.id.desc())
            .limit(50)
            .all()
        )
        return AdminAuditorDetailResponse(
            id=None,
            name="Built-in auditor",
            dob=None,
            email=settings.AUDITOR_ID,
            state=None,
            district=None,
            constituency=None,
            status="active",
            password_set=True,
            created_at=None,
            last_login_at=None,
            builtin=True,
            reviews_total=builtin_counts["reviews_total"],
            photos_approved=builtin_counts["photos_approved"],
            photos_rejected=builtin_counts["photos_rejected"],
            complaints_accepted=builtin_counts["complaints_accepted"],
            complaints_rejected=builtin_counts["complaints_rejected"],
            review_logs=[
                ReviewLogEntry(
                    kind=lg.kind,
                    target_id=lg.target_id,
                    decision=lg.decision,
                    created_at=lg.created_at,
                )
                for lg in logs
            ],
        )

    try:
        auditor_id = int(id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Auditor not found",
        )

    a = db.query(Auditor).filter(Auditor.id == auditor_id).first()
    if not a:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Auditor not found",
        )

    counts = _get_auditor_review_counts(db, a.email)
    logs = (
        db.query(ReviewLog)
        .filter(ReviewLog.auditor_ref == a.email)
        .order_by(ReviewLog.created_at.desc(), ReviewLog.id.desc())
        .limit(50)
        .all()
    )

    return AdminAuditorDetailResponse(
        id=a.id,
        name=a.name,
        dob=a.dob,
        email=a.email,
        state=a.state,
        district=a.district,
        constituency=a.constituency,
        status=a.status,
        password_set=bool(a.password_hash),
        created_at=a.created_at,
        last_login_at=a.last_login_at,
        builtin=False,
        reviews_total=counts["reviews_total"],
        photos_approved=counts["photos_approved"],
        photos_rejected=counts["photos_rejected"],
        complaints_accepted=counts["complaints_accepted"],
        complaints_rejected=counts["complaints_rejected"],
        review_logs=[
            ReviewLogEntry(
                kind=lg.kind,
                target_id=lg.target_id,
                decision=lg.decision,
                created_at=lg.created_at,
            )
            for lg in logs
        ],
    )
