import io
from pathlib import Path
from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import Submission, User, Work, XPLog
from app.services.otp import generate_otp_code, get_pending_secret


@pytest.fixture(autouse=True)
def enable_legacy_otp():
    old = settings.LEGACY_OTP_LOGIN_ENABLED
    settings.LEGACY_OTP_LOGIN_ENABLED = True
    yield
    settings.LEGACY_OTP_LOGIN_ENABLED = old


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_complete_verification_flow(client, db):
    # 1. OTP login flow
    email = "test.citizen.flow@gmail.com"

    # Clean previous run state for this email
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        db.query(XPLog).filter(XPLog.user_id == existing_user.id).delete()
        db.query(Submission).filter(Submission.user_id == existing_user.id).delete()
        db.delete(existing_user)
        db.commit()

    # Request OTP
    req_res = client.post("/auth/request-otp", json={"email": email})
    assert req_res.status_code == 200
    assert req_res.json()["message"] == "OTP sent"

    # Retrieve secret and generate OTP
    secret = get_pending_secret(email)
    assert secret is not None
    otp = generate_otp_code(secret)

    # Verify OTP
    verify_res = client.post("/auth/verify-otp", json={"email": email, "otp": otp})
    assert verify_res.status_code == 200
    auth_data = verify_res.json()
    user_token = auth_data["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # 2. Location set
    loc_res = client.put(
        "/me/location",
        headers=user_headers,
        json={"state": "Uttar Pradesh", "district": "PILIBHIT", "constituency": "PILIBHIT"},
    )
    assert loc_res.status_code == 200
    loc_data = loc_res.json()
    assert loc_data["state"] == "Uttar Pradesh"
    assert loc_data["district"] == "PILIBHIT"
    assert loc_data["constituency"] == "PILIBHIT"
    assert loc_data["xp"] == 0

    # 3. Works list
    works_res = client.get("/works?page=1&page_size=20", headers=user_headers)
    assert works_res.status_code == 200
    works_data = works_res.json()
    assert works_data["total"] > 0
    assert len(works_data["items"]) > 0

    target_work = works_data["items"][0]
    work_id = target_work["id"]

    # 4. Photo upload
    img = Image.new("RGB", (120, 120), color=(10, 180, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    files = {"photo": ("mplads_photo.jpg", buf.getvalue(), "image/jpeg")}
    data = {"lat": 28.63, "lng": 79.80}

    upload_res = client.post(
        f"/works/{work_id}/submissions",
        headers=user_headers,
        files=files,
        data=data,
    )
    assert upload_res.status_code == 200
    submission = upload_res.json()
    submission_id = submission["id"]
    assert submission["status"] == "pending"
    assert submission["work_id"] == work_id

    # 5. Auditor Login & Approve
    auditor_login_res = client.post(
        "/auth/auditor-login",
        json={"username": "auditor", "password": "auditor123"},
    )
    assert auditor_login_res.status_code == 200
    auditor_token = auditor_login_res.json()["access_token"]
    auditor_headers = {"Authorization": f"Bearer {auditor_token}"}

    # Approve submission
    approve_res = client.post(
        f"/auditor/submissions/{submission_id}/approve",
        headers=auditor_headers,
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "approved"

    # 6. XP equals 150
    me_res = client.get("/me", headers=user_headers)
    assert me_res.status_code == 200
    assert me_res.json()["xp"] == 150

    # Duplicate approval returns 409 and XP remains 150
    dup_res = client.post(
        f"/auditor/submissions/{submission_id}/approve",
        headers=auditor_headers,
    )
    assert dup_res.status_code == 409
    me_res_again = client.get("/me", headers=user_headers)
    assert me_res_again.json()["xp"] == 150

    # User cannot open image (403)
    user_img_res = client.get(
        f"/auditor/submissions/{submission_id}/image",
        headers=user_headers,
    )
    assert user_img_res.status_code == 403

    # Auditor can open image (200)
    auditor_img_res = client.get(
        f"/auditor/submissions/{submission_id}/image",
        headers=auditor_headers,
    )
    assert auditor_img_res.status_code == 200

    # 8. Reject another photo, retake, and upload again
    if len(works_data["items"]) > 1:
        target_work_2 = works_data["items"][1]
        work_id_2 = target_work_2["id"]

        # Upload photo for work 2
        img2 = Image.new("RGB", (100, 100), color=(200, 50, 50))
        buf2 = io.BytesIO()
        img2.save(buf2, format="JPEG")
        files2 = {"photo": ("mplads_photo_2.jpg", buf2.getvalue(), "image/jpeg")}
        upload_res_2 = client.post(
            f"/works/{work_id_2}/submissions",
            headers=user_headers,
            files=files2,
        )
        assert upload_res_2.status_code == 200
        submission_2 = upload_res_2.json()
        sub_2_id = submission_2["id"]

        # Auditor rejects it with reason
        reject_res = client.post(
            f"/auditor/submissions/{sub_2_id}/reject",
            headers=auditor_headers,
            json={"reason": "Plaque is blurry and unreadable"},
        )
        assert reject_res.status_code == 200
        assert reject_res.json()["status"] == "rejected"

        # User XP remains 150
        me_res_reject = client.get("/me", headers=user_headers)
        assert me_res_reject.json()["xp"] == 150

        # User retakes and uploads again (must succeed because previous is rejected)
        img2_retake = Image.new("RGB", (100, 100), color=(50, 200, 50))
        buf2_retake = io.BytesIO()
        img2_retake.save(buf2_retake, format="JPEG")
        files2_retake = {"photo": ("mplads_retake.jpg", buf2_retake.getvalue(), "image/jpeg")}
        retake_res = client.post(
            f"/works/{work_id_2}/submissions",
            headers=user_headers,
            files=files2_retake,
        )
        assert retake_res.status_code == 200
        assert retake_res.json()["status"] == "pending"

        # Clean up submission 2 image
        disk_path_2 = Path(__file__).resolve().parent.parent / retake_res.json()["image_path"]
        if disk_path_2.is_file():
            disk_path_2.unlink()

    # Clean up uploaded image file
    image_rel_path = submission["image_path"]
    disk_path = Path(__file__).resolve().parent.parent / image_rel_path
    if disk_path.is_file():
        disk_path.unlink()


def test_works_source_filter(client, db):
    # Log in test user
    email = "test.source.filter@gmail.com"
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        db.query(XPLog).filter(XPLog.user_id == existing_user.id).delete()
        db.query(Submission).filter(Submission.user_id == existing_user.id).delete()
        db.delete(existing_user)
        db.commit()

    client.post("/auth/request-otp", json={"email": email})
    secret = get_pending_secret(email)
    otp = generate_otp_code(secret)
    verify_res = client.post("/auth/verify-otp", json={"email": email, "otp": otp})
    user_headers = {"Authorization": f"Bearer {verify_res.json()['access_token']}"}

    client.put(
        "/me/location",
        headers=user_headers,
        json={"state": "Uttar Pradesh", "district": "PILIBHIT", "constituency": "PILIBHIT"},
    )

    # 1. Without source parameter: returns both
    all_res = client.get("/works?page=1&page_size=50", headers=user_headers)
    assert all_res.status_code == 200
    all_data = all_res.json()
    sources_in_all = {w["source"] for w in all_data["items"]}
    assert "LS" in sources_in_all
    assert "RS" in sources_in_all

    # 2. With source=LS: returns only LS
    ls_res = client.get("/works?source=LS&page=1&page_size=50", headers=user_headers)
    assert ls_res.status_code == 200
    ls_data = ls_res.json()
    assert len(ls_data["items"]) > 0
    assert all(w["source"] == "LS" for w in ls_data["items"])

    # 3. With source=RS: returns only RS
    rs_res = client.get("/works?source=RS&page=1&page_size=50", headers=user_headers)
    assert rs_res.status_code == 200
    rs_data = rs_res.json()
    assert len(rs_data["items"]) > 0
    assert all(w["source"] == "RS" for w in rs_data["items"])

    # 4. With invalid source: returns 400
    invalid_res = client.get("/works?source=XX", headers=user_headers)
    assert invalid_res.status_code == 400


def test_profile_stats_and_submissions(client, db):
    email_a = "test.profile.a@gmail.com"
    email_b = "test.profile.b@gmail.com"

    for email in (email_a, email_b):
        u = db.query(User).filter(User.email == email).first()
        if u:
            db.query(XPLog).filter(XPLog.user_id == u.id).delete()
            db.query(Submission).filter(Submission.user_id == u.id).delete()
            db.delete(u)
            db.commit()

    # User A login
    client.post("/auth/request-otp", json={"email": email_a})
    secret_a = get_pending_secret(email_a)
    otp_a = generate_otp_code(secret_a)
    auth_a = client.post("/auth/verify-otp", json={"email": email_a, "otp": otp_a}).json()
    headers_a = {"Authorization": f"Bearer {auth_a['access_token']}"}

    client.put(
        "/me/location",
        headers=headers_a,
        json={"state": "Uttar Pradesh", "district": "PILIBHIT", "constituency": "PILIBHIT"},
    )

    # Initial stats
    stats_0 = client.get("/me/stats", headers=headers_a).json()
    assert stats_0 == {"xp": 0, "approved": 0, "rejected": 0, "pending": 0}

    # User A submits work 1 and work 2
    works = client.get("/works?page=1&page_size=5", headers=headers_a).json()["items"]
    work_1_id = works[0]["id"]
    work_2_id = works[1]["id"]

    img_buf = io.BytesIO()
    Image.new("RGB", (64, 64), color="blue").save(img_buf, format="JPEG")

    sub_1 = client.post(
        f"/works/{work_1_id}/submissions",
        headers=headers_a,
        files={"photo": ("p1.jpg", img_buf.getvalue(), "image/jpeg")},
    ).json()

    sub_2 = client.post(
        f"/works/{work_2_id}/submissions",
        headers=headers_a,
        files={"photo": ("p2.jpg", img_buf.getvalue(), "image/jpeg")},
    ).json()

    # Auditor login
    aud_login = client.post(
        "/auth/auditor-login",
        json={"username": "auditor", "password": "auditor123"},
    ).json()
    aud_headers = {"Authorization": f"Bearer {aud_login['access_token']}"}

    # Approve sub_1
    client.post(f"/auditor/submissions/{sub_1['id']}/approve", headers=aud_headers)

    # Reject sub_2 with reason
    client.post(
        f"/auditor/submissions/{sub_2['id']}/reject",
        headers=aud_headers,
        json={"reason": "Incorrect work site photo"},
    )

    # Check /me/stats
    stats_after = client.get("/me/stats", headers=headers_a).json()
    assert stats_after["approved"] == 1
    assert stats_after["rejected"] == 1
    assert stats_after["pending"] == 0
    assert stats_after["xp"] == 150

    # Check /me/submissions?status=rejected
    rejected_subs_res = client.get("/me/submissions?status=rejected", headers=headers_a)
    assert rejected_subs_res.status_code == 200
    rejected_data = rejected_subs_res.json()
    assert rejected_data["total"] == 1
    assert len(rejected_data["items"]) == 1
    rej_item = rejected_data["items"][0]
    assert rej_item["status"] == "rejected"
    assert rej_item["reject_reason"] == "Incorrect work site photo"
    assert rej_item["xp_earned"] == 0
    assert "image_path" not in rej_item
    assert "image" not in rej_item

    # Check /me/submissions (default = "all")
    all_subs_res = client.get("/me/submissions", headers=headers_a)
    assert all_subs_res.status_code == 200
    all_subs_data = all_subs_res.json()
    assert all_subs_data["total"] == 2
    for item in all_subs_data["items"]:
        assert "image_path" not in item
        assert "image" not in item
        assert item["status"] in ("approved", "rejected")

    # User B login
    client.post("/auth/request-otp", json={"email": email_b})
    secret_b = get_pending_secret(email_b)
    otp_b = generate_otp_code(secret_b)
    auth_b = client.post("/auth/verify-otp", json={"email": email_b, "otp": otp_b}).json()
    headers_b = {"Authorization": f"Bearer {auth_b['access_token']}"}

    # User B cannot see User A's submissions
    user_b_subs = client.get("/me/submissions", headers=headers_b).json()
    assert user_b_subs["total"] == 0
    assert len(user_b_subs["items"]) == 0

    # Clean up uploaded files
    for s in (sub_1, sub_2):
        disk_p = Path(__file__).resolve().parent.parent / s["image_path"]
        if disk_p.is_file():
            disk_p.unlink()


