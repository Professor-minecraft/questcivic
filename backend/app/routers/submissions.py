from datetime import datetime
import io
from pathlib import Path
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from PIL import Image
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Submission, User, Work
from app.schemas import SubmissionResponse
from app.security import get_current_user
from app.services.csv_loader import normalize_text
from app.services.normalize import normalize_place
from app.services.storage import get_storage

router = APIRouter(tags=["submissions"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


@router.post("/works/{work_id}/submissions", response_model=SubmissionResponse)
async def create_submission(
    work_id: int,
    photo: UploadFile = File(...),
    lat: Optional[float] = Form(None),
    lng: Optional[float] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 1. Work must exist
    work = db.query(Work).filter(Work.id == work_id).first()
    if not work:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Work not found",
        )

    # 2. Work must match the user's location (otherwise 403)
    if not current_user.state or not current_user.district or not current_user.constituency:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User location not set",
        )

    user_state_norm = normalize_text(current_user.state)
    user_district_norm = normalize_text(current_user.district)
    user_constituency_norm = normalize_text(current_user.constituency)

    if work.source == "LS":
        matches = (
            work.state_norm == user_state_norm
            and work.district_norm == user_district_norm
            and work.constituency_norm == user_constituency_norm
        )
    else:  # RS
        matches = (
            work.state_norm == user_state_norm
            and work.district_norm == user_district_norm
        )

    if not matches:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Work does not match your location",
        )

    # 3. If user already has a pending or approved submission, return 409
    existing = (
        db.query(Submission)
        .filter(
            Submission.user_id == current_user.id,
            Submission.work_id == work.id,
            Submission.status.in_(["pending", "approved"]),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You already have a {existing.status} submission for this work.",
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
        folder="",
        content_type=content_type,
    )

    # 8. Create submission record (with location snapshot)
    submission = Submission(
        user_id=current_user.id,
        work_id=work.id,
        image_path=relative_path,
        status="pending",
        state_norm=normalize_place(current_user.state),
        constituency_norm=normalize_place(current_user.constituency),
        lat=lat,
        lng=lng,
        created_at=datetime.utcnow(),
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    return submission
