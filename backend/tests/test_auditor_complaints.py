import io
from pathlib import Path
from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.database import SessionLocal
from app.main import app
from app.models import Complaint, User, XPLog
from app.security import create_token, settings


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


def test_auditor_complaints_endpoints(client, db):
    # Setup test user
    user = db.query(User).filter(User.email == "test.auditor.user@gmail.com").first()
    if not user:
        user = User(
            email="test.auditor.user@gmail.com",
            otp_secret="JBSWY3DPEHPK3PXP",
            state="Uttar Pradesh",
            district="PILIBHIT",
            constituency="PILIBHIT",
            xp=100,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.state = "Uttar Pradesh"
        user.district = "PILIBHIT"
        user.constituency = "PILIBHIT"
        user.xp = 100
        db.commit()

    # Clean old complaints
    db.query(Complaint).filter(Complaint.user_id == user.id).delete(synchronize_session=False)
    db.commit()

    user_token = create_token(sub=str(user.id), role="user")
    auditor_token = create_token(sub=settings.AUDITOR_ID, role="auditor")

    h_user = {"Authorization": f"Bearer {user_token}"}
    h_auditor = {"Authorization": f"Bearer {auditor_token}"}

    # Count initial xp_log records
    initial_xplog_count = db.query(XPLog).count()

    # Create 2 complaints using the citizen endpoint
    def make_image_bytes():
        img = Image.new("RGB", (100, 100), color=(10, 20, 30))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()

    img_data = make_image_bytes()

    res_c1 = client.post(
        "/complaints",
        headers=h_user,
        files={"photo": ("c1.jpg", img_data, "image/jpeg")},
        data={"comment": "First complaint regarding broken canal water gate"},
    )
    assert res_c1.status_code == 200, res_c1.text
    c1_id = res_c1.json()["id"]

    res_c2 = client.post(
        "/complaints",
        headers=h_user,
        files={"photo": ("c2.jpg", img_data, "image/jpeg")},
        data={"comment": "Second complaint regarding unsafe hanging electricity wires"},
    )
    assert res_c2.status_code == 200, res_c2.text
    c2_id = res_c2.json()["id"]

    # --- REQUIREMENT: A user token must get 403 on all /auditor/complaints routes ---
    res_user_get = client.get("/auditor/complaints", headers=h_user)
    assert res_user_get.status_code == 403, f"Expected 403, got {res_user_get.status_code}"

    res_user_accept = client.post(f"/auditor/complaints/{c1_id}/accept", headers=h_user, json={"comment": "Valid comment"})
    assert res_user_accept.status_code == 403, f"Expected 403, got {res_user_accept.status_code}"

    res_user_reject = client.post(f"/auditor/complaints/{c2_id}/reject", headers=h_user, json={"comment": "Valid comment"})
    assert res_user_reject.status_code == 403, f"Expected 403, got {res_user_reject.status_code}"

    # --- REQUIREMENT: GET /auditor/complaints?status=pending|accepted|rejected|all&page=1&page_size=20 ---
    res_list = client.get("/auditor/complaints?status=pending&page=1&page_size=20", headers=h_auditor)
    assert res_list.status_code == 200, res_list.text
    data = res_list.json()
    assert "items" in data
    assert data["total"] >= 2
    assert len(data["items"]) >= 2

    # Check fields of each item
    item_c1 = next(it for it in data["items"] if it["id"] == c1_id)
    assert item_c1["id"] == c1_id
    assert item_c1["comment"] == "First complaint regarding broken canal water gate"
    assert item_c1["status"] == "pending"
    assert item_c1["auditor_comment"] is None
    assert item_c1["xp_awarded"] == 0
    assert item_c1["state"] == "Uttar Pradesh"
    assert item_c1["district"] == "PILIBHIT"
    assert item_c1["constituency"] == "PILIBHIT"
    assert "created_at" in item_c1
    assert "reviewed_at" in item_c1
    assert item_c1["user_email"] == "test.auditor.user@gmail.com"
    # Never include image_path
    assert "image_path" not in item_c1

    # Check invalid status returns 400
    res_inv_status = client.get("/auditor/complaints?status=invalid_status", headers=h_auditor)
    assert res_inv_status.status_code == 400

    # --- REQUIREMENT: Validation on accept/reject (Unknown ID: 404, comment < 3 chars or missing: 400 or 422) ---
    res_404 = client.post("/auditor/complaints/999999/accept", headers=h_auditor, json={"comment": "Valid comment"})
    assert res_404.status_code == 404

    res_short = client.post(f"/auditor/complaints/{c1_id}/accept", headers=h_auditor, json={"comment": "ok"})
    assert res_short.status_code in [400, 422]

    res_empty_trim = client.post(f"/auditor/complaints/{c1_id}/accept", headers=h_auditor, json={"comment": "   "})
    assert res_empty_trim.status_code in [400, 422]

    res_missing = client.post(f"/auditor/complaints/{c1_id}/accept", headers=h_auditor, json={})
    assert res_missing.status_code in [400, 422]

    # --- REQUIREMENT: Accepting a pending complaint raises that user's xp by exactly 50,
    # and GET /complaints/mine shows status accepted, the auditor_comment and xp_awarded 50 ---
    db.refresh(user)
    prev_xp = user.xp
    res_accept = client.post(
        f"/auditor/complaints/{c1_id}/accept",
        headers=h_auditor,
        json={"comment": "Verified with local irrigation authority. Complaint accepted."},
    )
    assert res_accept.status_code == 200, res_accept.text
    accepted_data = res_accept.json()
    assert accepted_data["status"] == "accepted"
    assert accepted_data["auditor_comment"] == "Verified with local irrigation authority. Complaint accepted."
    assert accepted_data["xp_awarded"] == 50

    db.refresh(user)
    assert user.xp == prev_xp + 50, f"Expected {prev_xp + 50}, got {user.xp}"

    # Verify citizen view on GET /complaints/mine
    res_mine = client.get("/complaints/mine?page=1&page_size=20", headers=h_user)
    assert res_mine.status_code == 200
    mine_items = res_mine.json()["items"]
    mine_c1 = next(it for it in mine_items if it["id"] == c1_id)
    assert mine_c1["status"] == "accepted"
    assert mine_c1["auditor_comment"] == "Verified with local irrigation authority. Complaint accepted."
    assert mine_c1["xp_awarded"] == 50

    # --- REQUIREMENT: Accepting the same complaint again returns 409 and the XP does not change ---
    res_accept_again = client.post(
        f"/auditor/complaints/{c1_id}/accept",
        headers=h_auditor,
        json={"comment": "Accepting second time should conflict"},
    )
    assert res_accept_again.status_code == 409, f"Expected 409, got {res_accept_again.status_code}"
    db.refresh(user)
    assert user.xp == prev_xp + 50

    # --- REQUIREMENT: Rejecting a pending complaint gives no XP and shows the auditor_comment to the user ---
    prev_xp_before_reject = user.xp
    res_reject = client.post(
        f"/auditor/complaints/{c2_id}/reject",
        headers=h_auditor,
        json={"comment": "Duplicate complaint already filed with electricity board."},
    )
    assert res_reject.status_code == 200, res_reject.text
    rejected_data = res_reject.json()
    assert rejected_data["status"] == "rejected"
    assert rejected_data["auditor_comment"] == "Duplicate complaint already filed with electricity board."
    assert rejected_data["xp_awarded"] == 0

    db.refresh(user)
    assert user.xp == prev_xp_before_reject

    # Verify citizen view for rejected complaint
    res_mine2 = client.get("/complaints/mine?page=1&page_size=20", headers=h_user)
    mine_items2 = res_mine2.json()["items"]
    mine_c2 = next(it for it in mine_items2 if it["id"] == c2_id)
    assert mine_c2["status"] == "rejected"
    assert mine_c2["auditor_comment"] == "Duplicate complaint already filed with electricity board."
    assert mine_c2["xp_awarded"] == 0

    # --- REQUIREMENT: If not pending, reject returns 409 ---
    res_reject_again = client.post(
        f"/auditor/complaints/{c2_id}/reject",
        headers=h_auditor,
        json={"comment": "Rejecting second time should conflict"},
    )
    assert res_reject_again.status_code == 409

    # --- REQUIREMENT: Do not write to xp_log for complaints ---
    current_xplog_count = db.query(XPLog).count()
    assert current_xplog_count == initial_xplog_count, "xp_log must not be modified for complaints!"
