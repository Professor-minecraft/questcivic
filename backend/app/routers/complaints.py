from datetime import datetime
import io
from pathlib import Path
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query, status
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy.orm import Session

from app.auth_deps import AuthUserOrAuditor, get_current_user_or_auditor
from app.config import settings
from app.database import get_db
from app.models import Auditor, Complaint, User
from app.schemas import ComplaintResponse, ComplaintsListResponse
from app.security import get_current_user
from app.services.normalize import normalize_place
from app.services.storage import get_storage

router = APIRouter(prefix="/complaints", tags=["complaints"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


@router.post("", response_model=ComplaintResponse)
async def create_complaint(
    photo: UploadFile = File(...),
    comment: str = Form(...),
    lat: Optional[float] = Form(None),
    lng: Optional[float] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 1. User must have a saved location
    if not current_user.state or not current_user.district or not current_user.constituency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Location not set",
        )

    # 2. Validate comment length (10 to 500 characters)
    clean_comment = comment.strip() if comment else ""
    if len(clean_comment) < 10 or len(clean_comment) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comment must be between 10 and 500 characters.",
        )

    # 3. Check pending complaints limit
    pending_count = (
        db.query(Complaint)
        .filter(
            Complaint.user_id == current_user.id,
            Complaint.status == "pending",
        )
        .count()
    )
    if pending_count >= settings.MAX_PENDING_COMPLAINTS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You already have {pending_count} pending complaints. Maximum allowed is {settings.MAX_PENDING_COMPLAINTS}.",
        )

    # 4. Check file extension
    original_ext = Path(photo.filename or "").suffix.lower()
    if original_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, or WebP images are allowed.",
        )

    # 5. Read contents and check MAX_UPLOAD_MB
    contents = await photo.read()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size allowed is {settings.MAX_UPLOAD_MB}MB.",
        )

    # 6. Verify with Pillow that it is a real image
    try:
        img = Image.open(io.BytesIO(contents))
        img.verify()
        if img.format not in ALLOWED_FORMATS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only JPEG, PNG, or WebP images are allowed.",
            )
        save_ext = ALLOWED_FORMATS[img.format]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is not a valid image.",
        )

    # 7. Save using storage abstraction (local disk or S3)
    random_filename = f"{uuid.uuid4().hex}{save_ext}"
    content_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(
        img.format, "image/jpeg"
    )
    storage = get_storage()
    relative_path = storage.save(
        file_bytes=contents,
        filename=random_filename,
        folder="complaints",
        content_type=content_type,
    )

    # 8. Create complaint record (location copied + normalized snapshot at time of complaint)
    complaint = Complaint(
        user_id=current_user.id,
        image_path=relative_path,
        comment=clean_comment,
        state=current_user.state,
        district=current_user.district,
        constituency=current_user.constituency,
        state_norm=normalize_place(current_user.state),
        constituency_norm=normalize_place(current_user.constituency),
        lat=lat,
        lng=lng,
        status="pending",
        auditor_comment=None,
        xp_awarded=0,
        created_at=datetime.utcnow(),
        reviewed_at=None,
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    return complaint


@router.get("/mine", response_model=ComplaintsListResponse)
def get_my_complaints(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Complaint)
        .filter(Complaint.user_id == current_user.id)
        .order_by(Complaint.created_at.desc(), Complaint.id.desc())
    )
    total = query.count()
    complaints = query.offset((page - 1) * page_size).limit(page_size).all()

    return ComplaintsListResponse(
        items=complaints,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{id}/image")
def get_complaint_image(
    id: int,
    auth: AuthUserOrAuditor = Depends(get_current_user_or_auditor),
    db: Session = Depends(get_db),
):
    complaint = db.query(Complaint).filter(Complaint.id == id).first()
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found",
        )

    # Allowed for auditor OR the user who owns the complaint. Anyone else gets 403.
    if not auth.is_auditor:
        if not auth.user or complaint.user_id != auth.user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You are not authorized to view this complaint's image",
            )
    else:
        # Auditor branch: DB auditors are scoped to their constituency
        auditor_id = auth.auditor_payload.get("auditor_id") if auth.auditor_payload else None
        if auditor_id is not None:
            auditor_row = db.query(Auditor).filter(Auditor.id == int(auditor_id)).first()
            if auditor_row:
                if (
                    normalize_place(auditor_row.state) != complaint.state_norm
                    or normalize_place(auditor_row.constituency) != complaint.constituency_norm
                ):
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Complaint not found",
                    )

    storage = get_storage()
    return storage.get_file_response(complaint.image_path)
