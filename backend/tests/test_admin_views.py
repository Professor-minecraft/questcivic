import io
from datetime import date, datetime
from pathlib import Path
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import Auditor, Complaint, ReviewLog, Submission, User, Work, XPLog
from app.security import create_token, init_admin_credentials, init_auditor_credentials


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
    img = Image.new("RGB", (60, 60), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_admin_routes_forbidden_for_user_and_auditor(client, db):
    user_h = _user_headers(user_id=1)
    auditor_h = _builtin_auditor_headers()

    routes_to_test = [
        ("GET", "/admin/users"),
        ("GET", "/admin/users/1"),
        ("GET", "/admin/submissions"),
        ("GET", "/admin/submissions/1/image"),
        ("GET", "/admin/complaints"),
        ("GET", "/admin/complaints/1/image"),
        ("GET", "/admin/auditors"),
        ("GET", "/admin/auditors/1"),
    ]

    for method, path in routes_to_test:
        r_user = client.get(path, headers=user_h)
        assert r_user.status_code == 403, f"User token must get 403 on {path}, got {r_user.status_code}"

        r_aud = client.get(path, headers=auditor_h)
        assert r_aud.status_code == 403, f"Auditor token must get 403 on {path}, got {r_aud.status_code}"


def test_review_log_and_auditor_counts_lifecycle(client, db):
    # Setup test user
    user = db.query(User).filter(User.email == "review.test.user@gmail.com").first()
    if not user:
        user = User(
            email="review.test.user@gmail.com",
            otp_secret="JBSWY3DPEHPK3PXP",
            state="Uttar Pradesh",
            district="PILIBHIT",
            constituency="PILIBHIT",
            xp=0,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    user_h = _user_headers(user.id)
    admin_h = _admin_headers()

    # Setup DB auditor
    db_auditor = db.query(Auditor).filter(Auditor.email == "dbauditor.review@gmail.com").first()
    if not db_auditor:
        db_auditor = Auditor(
            name="DB Review Auditor",
            dob=date(1991, 5, 20),
            email="dbauditor.review@gmail.com",
            state="Uttar Pradesh",
            district="PILIBHIT",
            constituency="PILIBHIT",
            status="active",
            password_hash="$2b$12$somehash",
        )
        db.add(db_auditor)
        db.commit()
        db.refresh(db_auditor)

    db_aud_h = _db_auditor_headers(db_auditor.id, db_auditor.email)

    # 1. Clean previous review logs for db_auditor
    db.query(ReviewLog).filter(ReviewLog.auditor_ref == db_auditor.email).delete()
    db.commit()

    # 2. Create a photo submission for a work matching the user's location
    work = (
        db.query(Work)
        .filter(
            Work.state_norm == user.state.strip().upper(),
            Work.district_norm == user.district.strip().upper(),
            Work.constituency_norm == user.constituency.strip().upper(),
        )
        .first()
    )
    if not work:
        work = (
            db.query(Work)
            .filter(
                Work.state_norm == user.state.strip().upper(),
                Work.district_norm == user.district.strip().upper(),
            )
            .first()
        )
    assert work is not None, "Need at least one matching work in database"

    img_data = _create_sample_image()
    sub_res = client.post(
        f"/works/{work.id}/submissions",
        headers=user_h,
        files={"photo": ("test.jpg", img_data, "image/jpeg")},
    )
    # If conflict (already submitted), fetch it or update status to pending
    if sub_res.status_code == 409:
        sub = db.query(Submission).filter(Submission.user_id == user.id, Submission.work_id == work.id).first()
        sub.status = "pending"
        db.commit()
        sub_id = sub.id
    else:
        assert sub_res.status_code == 200
        sub_id = sub_res.json()["id"]

    # 3. Approve submission as DB auditor -> adds ONE ReviewLog row
    initial_log_count = db.query(ReviewLog).filter(
        ReviewLog.auditor_ref == db_auditor.email,
        ReviewLog.kind == "submission",
        ReviewLog.decision == "approved",
    ).count()

    approve_res = client.post(f"/auditor/submissions/{sub_id}/approve", headers=db_aud_h)
    assert approve_res.status_code == 200
    app_data = approve_res.json()
    assert app_data["status"] == "approved"
    # Verify response structure remains unchanged
    assert "id" in app_data
    assert "image_path" in app_data

    new_log_count = db.query(ReviewLog).filter(
        ReviewLog.auditor_ref == db_auditor.email,
        ReviewLog.kind == "submission",
        ReviewLog.decision == "approved",
    ).count()
    assert new_log_count == initial_log_count + 1, "ReviewLog must have exactly 1 new approved submission row"

    # 4. Verify it appears in that auditor's counts on GET /admin/auditors
    auditors_res = client.get("/admin/auditors", headers=admin_h)
    assert auditors_res.status_code == 200
    aud_items = auditors_res.json()["items"]
    target_aud = next(a for a in aud_items if a["email"] == db_auditor.email)
    assert target_aud["photos_approved"] >= 1
    assert target_aud["reviews_total"] >= 1
    assert target_aud["builtin"] is False

    # Also verify built-in auditor is first
    assert aud_items[0]["builtin"] is True
    assert aud_items[0]["email"] == settings.AUDITOR_ID

    # 5. Verify GET /admin/auditors/{id}
    detail_res = client.get(f"/admin/auditors/{db_auditor.id}", headers=admin_h)
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["id"] == db_auditor.id
    assert detail_data["photos_approved"] >= 1
    assert "review_logs" in detail_data
    assert len(detail_data["review_logs"]) >= 1
    first_log = detail_data["review_logs"][0]
    assert first_log["kind"] == "submission"
    assert first_log["decision"] == "approved"
    assert first_log["target_id"] == sub_id


def test_complaints_review_log_and_rejection(client, db):
    user = db.query(User).filter(User.email == "review.test.user@gmail.com").first()
    user_h = _user_headers(user.id)
    admin_h = _admin_headers()

    db_auditor = db.query(Auditor).filter(Auditor.email == "dbauditor.review@gmail.com").first()
    db_aud_h = _db_auditor_headers(db_auditor.id, db_auditor.email)

    # 1. User files a complaint
    img_data = _create_sample_image()
    comp_res = client.post(
        "/complaints",
        headers=user_h,
        files={"photo": ("comp.jpg", img_data, "image/jpeg")},
        data={"comment": "Broken road surface with large potholes"},
    )
    if comp_res.status_code != 200:
        # User might have hit pending complaints limit, clean up old pending
        db.query(Complaint).filter(Complaint.user_id == user.id, Complaint.status == "pending").delete()
        db.commit()
        comp_res = client.post(
            "/complaints",
            headers=user_h,
            files={"photo": ("comp.jpg", img_data, "image/jpeg")},
            data={"comment": "Broken road surface with large potholes"},
        )
    assert comp_res.status_code == 200
    comp_id = comp_res.json()["id"]

    # 2. DB auditor accepts complaint
    init_comp_acc = db.query(ReviewLog).filter(
        ReviewLog.auditor_ref == db_auditor.email,
        ReviewLog.kind == "complaint",
        ReviewLog.decision == "accepted",
    ).count()

    acc_res = client.post(f"/auditor/complaints/{comp_id}/accept", headers=db_aud_h, json={"comment": "Verified and accepted."})
    assert acc_res.status_code == 200
    acc_data = acc_res.json()
    assert acc_data["status"] == "accepted"

    new_comp_acc = db.query(ReviewLog).filter(
        ReviewLog.auditor_ref == db_auditor.email,
        ReviewLog.kind == "complaint",
        ReviewLog.decision == "accepted",
    ).count()
    assert new_comp_acc == init_comp_acc + 1

    # 3. User files second complaint and DB auditor rejects it
    comp_res2 = client.post(
        "/complaints",
        headers=user_h,
        files={"photo": ("comp2.jpg", img_data, "image/jpeg")},
        data={"comment": "Street light issue reported on main crossroad"},
    )
    assert comp_res2.status_code == 200
    comp2_id = comp_res2.json()["id"]

    rej_res = client.post(f"/auditor/complaints/{comp2_id}/reject", headers=db_aud_h, json={"comment": "Out of jurisdiction."})
    assert rej_res.status_code == 200

    # 4. Check admin views for complaints
    admin_comp_res = client.get("/admin/complaints?status=all", headers=admin_h)
    assert admin_comp_res.status_code == 200
    c_data = admin_comp_res.json()
    assert "items" in c_data
    comp_item = next(c for c in c_data["items"] if c["id"] == comp_id)
    assert comp_item["status"] == "accepted"
    assert comp_item["auditor_comment"] == "Verified and accepted."
    assert "image_path" not in comp_item

    # 5. Image endpoint opens for admin
    img_resp = client.get(f"/admin/complaints/{comp_id}/image", headers=admin_h)
    assert img_resp.status_code == 200
    assert img_resp.headers["content-type"].startswith("image/")


def test_admin_views_security_no_sensitive_fields(client, db):
    admin_h = _admin_headers()

    # GET /admin/users
    r_users = client.get("/admin/users", headers=admin_h)
    assert r_users.status_code == 200
    text_users = r_users.text
    assert "otp_secret" not in text_users
    assert "password_hash" not in text_users
    assert "image_path" not in text_users
    # DOB must not appear in user endpoints
    assert "dob" not in text_users

    # GET /admin/users/{id}
    u = db.query(User).first()
    if u:
        r_user_detail = client.get(f"/admin/users/{u.id}", headers=admin_h)
        assert r_user_detail.status_code == 200
        text_u = r_user_detail.text
        assert "otp_secret" not in text_u
        assert "password_hash" not in text_u
        assert "image_path" not in text_u
        assert "dob" not in text_u

    # GET /admin/submissions
    r_subs = client.get("/admin/submissions", headers=admin_h)
    assert r_subs.status_code == 200
    text_subs = r_subs.text
    assert "image_path" not in text_subs
    assert "password_hash" not in text_subs
    assert "otp_secret" not in text_subs

    # GET /admin/complaints
    r_comps = client.get("/admin/complaints", headers=admin_h)
    assert r_comps.status_code == 200
    text_comps = r_comps.text
    assert "image_path" not in text_comps
    assert "password_hash" not in text_comps
    assert "otp_secret" not in text_comps

    # GET /admin/auditors
    r_auds = client.get("/admin/auditors", headers=admin_h)
    assert r_auds.status_code == 200
    text_auds = r_auds.text
    assert "password_hash" not in text_auds
    assert "invite_token_hash" not in text_auds
    assert "token" not in text_auds or "access_token" not in text_auds
    assert "otp_secret" not in text_auds
    assert "image_path" not in text_auds


def test_submission_image_opens_for_admin(client, db):
    admin_h = _admin_headers()
    sub = db.query(Submission).first()
    if sub:
        r_img = client.get(f"/admin/submissions/{sub.id}/image", headers=admin_h)
        assert r_img.status_code in (200, 404)  # 200 if file exists on disk
        if r_img.status_code == 200:
            assert r_img.headers["content-type"].startswith("image/")

    # 404 for unknown submission
    assert client.get("/admin/submissions/999999/image", headers=admin_h).status_code == 404
    assert client.get("/admin/complaints/999999/image", headers=admin_h).status_code == 404
