import io
from pathlib import Path
from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.database import SessionLocal
from app.main import app
from app.models import Complaint, User
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


def test_complaints_flow(client, db):
    # Setup test users
    user1 = db.query(User).filter(User.email == "complaint.user1@gmail.com").first()
    if not user1:
        user1 = User(
            email="complaint.user1@gmail.com",
            otp_secret="JBSWY3DPEHPK3PXP",
            state="Uttar Pradesh",
            district="PILIBHIT",
            constituency="PILIBHIT",
        )
        db.add(user1)
        db.commit()
        db.refresh(user1)
    else:
        user1.state = "Uttar Pradesh"
        user1.district = "PILIBHIT"
        user1.constituency = "PILIBHIT"
        db.commit()

    user2 = db.query(User).filter(User.email == "complaint.user2@gmail.com").first()
    if not user2:
        user2 = User(
            email="complaint.user2@gmail.com",
            otp_secret="JBSWY3DPEHPK3PXP",
            state="Bihar",
            district="ARARIA",
            constituency="ARARIA",
        )
        db.add(user2)
        db.commit()
        db.refresh(user2)

    user_no_loc = db.query(User).filter(User.email == "complaint.noloc@gmail.com").first()
    if not user_no_loc:
        user_no_loc = User(
            email="complaint.noloc@gmail.com",
            otp_secret="JBSWY3DPEHPK3PXP",
            state=None,
            district=None,
            constituency=None,
        )
        db.add(user_no_loc)
        db.commit()
        db.refresh(user_no_loc)
    else:
        user_no_loc.state = None
        user_no_loc.district = None
        user_no_loc.constituency = None
        db.commit()

    # Clean existing complaints for these test users
    db.query(Complaint).filter(
        Complaint.user_id.in_([user1.id, user2.id, user_no_loc.id])
    ).delete(synchronize_session=False)
    db.commit()

    user1_token = create_token(sub=str(user1.id), role="user")
    user2_token = create_token(sub=str(user2.id), role="user")
    noloc_token = create_token(sub=str(user_no_loc.id), role="user")
    auditor_token = create_token(sub=settings.AUDITOR_ID, role="auditor")

    h1 = {"Authorization": f"Bearer {user1_token}"}
    h2 = {"Authorization": f"Bearer {user2_token}"}
    hnoloc = {"Authorization": f"Bearer {noloc_token}"}
    hauditor = {"Authorization": f"Bearer {auditor_token}"}

    def make_image_bytes():
        img = Image.new("RGB", (100, 100), color=(50, 100, 150))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()

    valid_img = make_image_bytes()

    # 1. User without saved location gets 400 "Location not set"
    res_noloc = client.post(
        "/complaints",
        headers=hnoloc,
        files={"photo": ("photo.jpg", valid_img, "image/jpeg")},
        data={"comment": "Valid comment but no location set"},
    )
    assert res_noloc.status_code == 400
    assert res_noloc.json()["detail"] == "Location not set"

    # 2. Comment shorter than 10 characters returns 400
    res_short = client.post(
        "/complaints",
        headers=h1,
        files={"photo": ("photo.jpg", valid_img, "image/jpeg")},
        data={"comment": "Too short"},
    )
    assert res_short.status_code == 400

    # 3. A .txt file renamed to .jpg returns 400
    fake_img = b"This is plain text not an image."
    res_fake = client.post(
        "/complaints",
        headers=h1,
        files={"photo": ("fake.jpg", fake_img, "image/jpeg")},
        data={"comment": "A proper comment longer than ten chars"},
    )
    assert res_fake.status_code == 400
    assert "not a valid image" in res_fake.json()["detail"].lower()

    # 4. User with saved location creates complaint and it comes back as pending
    res_c1 = client.post(
        "/complaints",
        headers=h1,
        files={"photo": ("pic1.jpg", valid_img, "image/jpeg")},
        data={"comment": "Complaint number one about broken road", "lat": 28.6, "lng": 79.8},
    )
    assert res_c1.status_code == 200
    c1_data = res_c1.json()
    assert c1_data["status"] == "pending"
    assert c1_data["state"] == "Uttar Pradesh"
    assert c1_data["district"] == "PILIBHIT"
    assert c1_data["constituency"] == "PILIBHIT"
    assert c1_data["comment"] == "Complaint number one about broken road"
    assert c1_data["auditor_comment"] is None
    assert c1_data["xp_awarded"] == 0
    assert "created_at" in c1_data
    assert "reviewed_at" in c1_data
    assert "image_path" not in c1_data  # Never include image_path

    c1_id = c1_data["id"]

    # Create 2nd and 3rd pending complaints
    res_c2 = client.post(
        "/complaints",
        headers=h1,
        files={"photo": ("pic2.jpg", valid_img, "image/jpeg")},
        data={"comment": "Complaint number two about water logging"},
    )
    assert res_c2.status_code == 200

    res_c3 = client.post(
        "/complaints",
        headers=h1,
        files={"photo": ("pic3.jpg", valid_img, "image/jpeg")},
        data={"comment": "Complaint number three about street lights"},
    )
    assert res_c3.status_code == 200

    # 5. A 4th pending complaint returns 409
    res_c4 = client.post(
        "/complaints",
        headers=h1,
        files={"photo": ("pic4.jpg", valid_img, "image/jpeg")},
        data={"comment": "Complaint number four should be rejected with 409"},
    )
    assert res_c4.status_code == 409
    assert "maximum" in res_c4.json()["detail"].lower() or "pending" in res_c4.json()["detail"].lower()

    # Create complaint for user2
    res_u2 = client.post(
        "/complaints",
        headers=h2,
        files={"photo": ("pic_u2.jpg", valid_img, "image/jpeg")},
        data={"comment": "User two complaint in Araria district"},
    )
    assert res_u2.status_code == 200
    c_u2_id = res_u2.json()["id"]

    # 6. GET /complaints/mine shows only that user's complaints
    mine_res = client.get("/complaints/mine?page=1&page_size=20", headers=h1)
    assert mine_res.status_code == 200
    mine_data = mine_res.json()
    assert mine_data["total"] == 3
    assert len(mine_data["items"]) == 3
    ids = [item["id"] for item in mine_data["items"]]
    assert c1_id in ids
    assert c_u2_id not in ids
    for item in mine_data["items"]:
        assert "image_path" not in item

    # 7. Image access permissions:
    # The owner can open the image
    img_owner = client.get(f"/complaints/{c1_id}/image", headers=h1)
    assert img_owner.status_code == 200
    assert img_owner.headers["content-type"].startswith("image/")

    # Another user gets 403
    img_other = client.get(f"/complaints/{c1_id}/image", headers=h2)
    assert img_other.status_code == 403

    # The auditor can open it
    img_auditor = client.get(f"/complaints/{c1_id}/image", headers=hauditor)
    assert img_auditor.status_code == 200
    assert img_auditor.headers["content-type"].startswith("image/")

    # Unknown id gets 404
    img_unknown = client.get("/complaints/999999/image", headers=h1)
    assert img_unknown.status_code == 404
