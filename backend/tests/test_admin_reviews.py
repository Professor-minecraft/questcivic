"""
Tests for Admin Reviews and Auditor Summaries:
- GET /admin/reviews with all filters
- GET /admin/auditors/{id}/summary
- Extra fields on GET /admin/users, GET /admin/submissions, GET /admin/complaints
- Role checks: user/auditor get 403
- Security checks: no image_path, password, or secrets
"""
import io
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import Auditor, Complaint, ReviewLog, Submission, User, Work, XPLog
from app.security import create_token, init_admin_credentials, init_auditor_credentials

KOLKATA_TZ = ZoneInfo("Asia/Kolkata")


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def setup_credentials():
    init_auditor_credentials()
    init_admin_credentials()


def _admin_headers():
    token = create_token(sub=settings.ADMIN_ID, role="admin")
    return {"Authorization": f"Bearer {token}"}


def _builtin_auditor_headers():
    token = create_token(sub=settings.AUDITOR_ID, role="auditor")
    return {"Authorization": f"Bearer {token}"}


def _db_auditor_headers(auditor_id: int, email: str):
    token = create_token(sub=email, role="auditor", extra={"auditor_id": auditor_id})
    return {"Authorization": f"Bearer {token}"}


def _user_headers(user_id: int):
    token = create_token(sub=str(user_id), role="user")
    return {"Authorization": f"Bearer {token}"}


def _create_sample_image():
    img = Image.new("RGB", (50, 50), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Test Auth Guard (User & Auditor get 403)
# ---------------------------------------------------------------------------

def test_admin_reviews_forbidden_for_user_and_auditor(client):
    user_h = _user_headers(1)
    auditor_h = _builtin_auditor_headers()

    endpoints = [
        "/admin/reviews",
        "/admin/auditors/builtin/summary",
        "/admin/auditors/1/summary",
    ]
    for ep in endpoints:
        r_user = client.get(ep, headers=user_h)
        assert r_user.status_code == 403, f"Expected 403 for user on {ep}, got {r_user.status_code}"

        r_aud = client.get(ep, headers=auditor_h)
        assert r_aud.status_code == 403, f"Expected 403 for auditor on {ep}, got {r_aud.status_code}"


# ---------------------------------------------------------------------------
# Test Existing Admin Routes (TASK 1: extra fields)
# ---------------------------------------------------------------------------

def test_existing_admin_routes_extra_fields(client, db):
    admin_h = _admin_headers()

    # 1. Setup user with a name and complaints
    user = db.query(User).filter(User.email == "extra.fields.user@gmail.com").first()
    if not user:
        user = User(
            email="extra.fields.user@gmail.com",
            name="Extra Fields Citizen",
            otp_secret="SECRETTEST123",
            state="Uttar Pradesh",
            district="PILIBHIT",
            constituency="PILIBHIT",
            xp=50,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Add a rejected complaint and pending complaint for this user
    comp_rej = Complaint(
        user_id=user.id,
        image_path="uploads/test_comp_rej.jpg",
        comment="Damaged road near market",
        state="Uttar Pradesh",
        district="PILIBHIT",
        constituency="PILIBHIT",
        status="rejected",
        auditor_comment="Not visible",
        created_at=datetime.utcnow() - timedelta(minutes=30),
        reviewed_at=datetime.utcnow() - timedelta(minutes=5),
    )
    comp_pend = Complaint(
        user_id=user.id,
        image_path="uploads/test_comp_pend.jpg",
        comment="Broken water pipeline",
        state="Uttar Pradesh",
        district="PILIBHIT",
        constituency="PILIBHIT",
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add_all([comp_rej, comp_pend])
    db.commit()

    # Log review for comp_rej
    log_comp = ReviewLog(
        auditor_ref=settings.AUDITOR_ID,
        kind="complaint",
        target_id=comp_rej.id,
        decision="rejected",
        created_at=datetime.utcnow() - timedelta(minutes=5),
    )
    db.add(log_comp)
    db.commit()

    # Test GET /admin/users
    res_users = client.get(f"/admin/users?search={user.email}", headers=admin_h)
    assert res_users.status_code == 200
    user_item = next(u for u in res_users.json()["items"] if u["id"] == user.id)
    assert user_item["name"] == "Extra Fields Citizen"
    assert user_item["complaints_rejected"] >= 1
    assert user_item["complaints_pending"] >= 1

    # Test GET /admin/users/{id}
    res_user = client.get(f"/admin/users/{user.id}", headers=admin_h)
    assert res_user.status_code == 200
    data_user = res_user.json()
    assert data_user["name"] == "Extra Fields Citizen"
    assert data_user["complaints_rejected"] >= 1
    assert data_user["complaints_pending"] >= 1

    # Test GET /admin/complaints contains user_name and reviewed_by
    res_comps = client.get(f"/admin/complaints?user_id={user.id}", headers=admin_h)
    assert res_comps.status_code == 200
    comps_items = res_comps.json()["items"]
    
    # Checked rejected complaint has reviewed_by
    rej_item = next(c for c in comps_items if c["id"] == comp_rej.id)
    assert rej_item["user_name"] == "Extra Fields Citizen"
    assert rej_item["reviewed_by"] is not None
    assert rej_item["reviewed_by"]["builtin"] is True
    assert rej_item["reviewed_by"]["email"] == settings.AUDITOR_ID

    # Checked pending complaint has null reviewed_by
    pend_item = next(c for c in comps_items if c["id"] == comp_pend.id)
    assert pend_item["user_name"] == "Extra Fields Citizen"
    assert pend_item["reviewed_by"] is None


# ---------------------------------------------------------------------------
# Test Two Auditors Reviews Flow & Summary (TASK 2 & TASK 3)
# ---------------------------------------------------------------------------

def test_reviews_flow_filters_and_auditor_summary(client, db):
    admin_h = _admin_headers()
    builtin_aud_h = _builtin_auditor_headers()

    # 1. Setup User
    user = db.query(User).filter(User.email == "review.target.user@gmail.com").first()
    if not user:
        user = User(
            email="review.target.user@gmail.com",
            name="Alice Review Target",
            otp_secret="SECRETTARGET123",
            state="Uttar Pradesh",
            district="PILIBHIT",
            constituency="PILIBHIT",
            xp=0,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    user_h = _user_headers(user.id)

    # 2. Setup DB Auditor
    db_aud = db.query(Auditor).filter(Auditor.email == "auditor.staff.two@gmail.com").first()
    if not db_aud:
        db_aud = Auditor(
            name="Staff Auditor Beta",
            dob=date(1992, 8, 15),
            email="auditor.staff.two@gmail.com",
            state="Uttar Pradesh",
            district="PILIBHIT",
            constituency="PILIBHIT",
            status="active",
            password_hash="$2b$12$somevalidhashhere",
        )
        db.add(db_aud)
        db.commit()
        db.refresh(db_aud)

    db_aud_h = _db_auditor_headers(db_aud.id, db_aud.email)

    # 3. Clean up review logs for these two auditors so counts are deterministic
    db.query(ReviewLog).filter(
        ReviewLog.auditor_ref.in_([settings.AUDITOR_ID, db_aud.email])
    ).delete()
    db.commit()

    work = db.query(Work).filter(
        Work.source == "LS",
        Work.state_norm == "UTTAR PRADESH",
        Work.district_norm == "PILIBHIT",
        Work.constituency_norm == "PILIBHIT",
    ).first()
    assert work is not None

    # Create submission 1: approved by built-in auditor
    img_data = _create_sample_image()
    sub1_res = client.post(
        f"/works/{work.id}/submissions",
        headers=user_h,
        files={"photo": ("sub1.jpg", img_data, "image/jpeg")},
    )
    if sub1_res.status_code == 409:
        sub1 = db.query(Submission).filter(Submission.user_id == user.id, Submission.work_id == work.id).first()
        sub1.status = "pending"
        db.commit()
        sub1_id = sub1.id
    else:
        sub1_id = sub1_res.json()["id"]

    # Builtin auditor approves sub1
    res_app = client.post(f"/auditor/submissions/{sub1_id}/approve", headers=builtin_aud_h)
    assert res_app.status_code == 200

    # Create submission 2: rejected by DB auditor
    from app.services.normalize import normalize_place
    sub2 = Submission(
        user_id=user.id,
        work_id=work.id,
        image_path="uploads/sub2_test.jpg",
        status="pending",
        state_norm=normalize_place(work.state),
        constituency_norm=normalize_place(work.constituency),
        created_at=datetime.utcnow() - timedelta(minutes=10),
    )
    db.add(sub2)
    db.commit()
    db.refresh(sub2)

    # DB auditor rejects sub2
    res_rej = client.post(
        f"/auditor/submissions/{sub2.id}/reject",
        headers=db_aud_h,
        json={"reason": "Blurry photo of work site"},
    )
    assert res_rej.status_code == 200

    # Create Complaint 1: accepted by DB auditor
    comp1 = Complaint(
        user_id=user.id,
        image_path="uploads/comp1_test.jpg",
        comment="Fallen streetlight pole on main crossroad",
        state="Uttar Pradesh",
        district="PILIBHIT",
        constituency="PILIBHIT",
        state_norm="UTTAR PRADESH",
        constituency_norm="PILIBHIT",
        status="pending",
        created_at=datetime.utcnow() - timedelta(minutes=20),
    )
    db.add(comp1)
    db.commit()
    db.refresh(comp1)

    # DB auditor accepts complaint 1
    res_comp_acc = client.post(
        f"/auditor/complaints/{comp1.id}/accept",
        headers=db_aud_h,
        json={"comment": "Verified and forwarded to PWD"},
    )
    assert res_comp_acc.status_code == 200

    # Create Complaint 2: rejected by built-in auditor
    comp2 = Complaint(
        user_id=user.id,
        image_path="uploads/comp2_test.jpg",
        comment="Minor trash in private garden area",
        state="Uttar Pradesh",
        district="PILIBHIT",
        constituency="PILIBHIT",
        status="pending",
        created_at=datetime.utcnow() - timedelta(minutes=15),
    )
    db.add(comp2)
    db.commit()
    db.refresh(comp2)

    res_comp_rej = client.post(
        f"/auditor/complaints/{comp2.id}/reject",
        headers=builtin_aud_h,
        json={"comment": "Private property, not covered by municipal works"},
    )
    assert res_comp_rej.status_code == 200

    # -----------------------------------------------------------------------
    # Verification of GET /admin/reviews
    # -----------------------------------------------------------------------
    all_revs_res = client.get("/admin/reviews", headers=admin_h)
    assert all_revs_res.status_code == 200
    all_revs = all_revs_res.json()
    assert all_revs["total"] >= 4
    items = all_revs["items"]

    # Security check: no image_path or passwords in response
    text_resp = all_revs_res.text
    assert "image_path" not in text_resp
    assert "password_hash" not in text_resp
    assert "otp_secret" not in text_resp

    # Check item structure on newest item
    newest = items[0]
    for field in [
        "review_id", "created_at", "auditor", "kind", "decision", "target_id",
        "title", "user", "state", "district", "constituency", "comment",
        "submitted_at", "review_minutes"
    ]:
        assert field in newest, f"Field '{field}' must be in review item"

    assert "id" in newest["auditor"]
    assert "name" in newest["auditor"]
    assert "email" in newest["auditor"]
    assert "builtin" in newest["auditor"]
    assert "id" in newest["user"]
    assert "name" in newest["user"]
    assert "email" in newest["user"]

    # Check rejected photo has reject_reason as comment
    rej_photo_item = next(i for i in items if i["target_id"] == sub2.id and i["kind"] == "submission")
    assert rej_photo_item["comment"] == "Blurry photo of work site"
    assert rej_photo_item["auditor"]["builtin"] is False
    assert rej_photo_item["auditor"]["email"] == db_aud.email
    assert rej_photo_item["user"]["email"] == user.email

    # Check approved photo has comment is null
    app_photo_item = next(i for i in items if i["target_id"] == sub1_id and i["kind"] == "submission")
    assert app_photo_item["comment"] is None
    assert app_photo_item["auditor"]["builtin"] is True

    # Check accepted complaint has auditor_comment and truncated title (up to 80 chars)
    acc_comp_item = next(i for i in items if i["target_id"] == comp1.id and i["kind"] == "complaint")
    assert acc_comp_item["comment"] == "Verified and forwarded to PWD"
    assert acc_comp_item["title"] == comp1.comment[:80]
    assert acc_comp_item["decision"] == "accepted"

    # -----------------------------------------------------------------------
    # Test Filters on GET /admin/reviews
    # -----------------------------------------------------------------------

    # Filter by auditor=builtin
    builtin_filter_res = client.get("/admin/reviews?auditor_id=builtin", headers=admin_h)
    assert builtin_filter_res.status_code == 200
    b_items = builtin_filter_res.json()["items"]
    assert all(i["auditor"]["builtin"] is True for i in b_items)

    # Filter by auditor=<db_aud.id>
    dbaud_filter_res = client.get(f"/admin/reviews?auditor_id={db_aud.id}", headers=admin_h)
    assert dbaud_filter_res.status_code == 200
    d_items = dbaud_filter_res.json()["items"]
    assert all(i["auditor"]["email"] == db_aud.email for i in d_items)
    assert len(d_items) == 2  # sub2 reject and comp1 accept

    # Filter by user_id
    user_filter_res = client.get(f"/admin/reviews?user_id={user.id}", headers=admin_h)
    assert user_filter_res.status_code == 200
    u_items = user_filter_res.json()["items"]
    assert all(i["user"]["id"] == user.id for i in u_items)

    # Filter by kind=complaint
    kind_comp_res = client.get("/admin/reviews?kind=complaint", headers=admin_h)
    assert kind_comp_res.status_code == 200
    assert all(i["kind"] == "complaint" for i in kind_comp_res.json()["items"])

    # Filter by decision=rejected
    dec_rej_res = client.get("/admin/reviews?decision=rejected", headers=admin_h)
    assert dec_rej_res.status_code == 200
    assert all(i["decision"] == "rejected" for i in dec_rej_res.json()["items"])

    # Filter by range=today
    today_res = client.get("/admin/reviews?range=today", headers=admin_h)
    assert today_res.status_code == 200
    assert today_res.json()["total"] >= 4

    # -----------------------------------------------------------------------
    # Verification of GET /admin/auditors/{id}/summary (TASK 3)
    # -----------------------------------------------------------------------

    # 1. Unknown auditor returns 404
    res_404 = client.get("/admin/auditors/999999/summary", headers=admin_h)
    assert res_404.status_code == 404
    assert res_404.json()["detail"] == "Auditor not found"

    # 2. Builtin auditor summary
    builtin_sum_res = client.get("/admin/auditors/builtin/summary", headers=admin_h)
    assert builtin_sum_res.status_code == 200
    bs = builtin_sum_res.json()
    assert bs["reviews_total"] == 2
    assert bs["photos_approved"] == 1
    assert bs["photos_rejected"] == 0
    assert bs["complaints_accepted"] == 0
    assert bs["complaints_rejected"] == 1
    assert bs["approval_rate"] == 0.5  # 1 approved / 2 total = 0.5
    assert bs["avg_review_minutes"] is not None
    assert bs["first_review_at"] is not None
    assert bs["last_review_at"] is not None
    assert len(bs["per_day"]) == 30, f"per_day must have 30 entries, got {len(bs['per_day'])}"
    assert all("date" in d and "count" in d for d in bs["per_day"])

    # 3. DB auditor summary
    dbaud_sum_res = client.get(f"/admin/auditors/{db_aud.id}/summary", headers=admin_h)
    assert dbaud_sum_res.status_code == 200
    ds = dbaud_sum_res.json()
    assert ds["reviews_total"] == 2
    assert ds["photos_approved"] == 0
    assert ds["photos_rejected"] == 1
    assert ds["complaints_accepted"] == 1
    assert ds["complaints_rejected"] == 0
    assert ds["approval_rate"] == 0.5  # 1 accepted / 2 total = 0.5
    assert len(ds["per_day"]) == 30
