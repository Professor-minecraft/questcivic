import io
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from PIL import Image

from app.database import SessionLocal
from app.main import app
from app.models import Complaint, User
from app.security import create_token, settings


def run_verification():
    print("=== STARTING COMPLAINTS VERIFICATION ===")
    with TestClient(app) as client:
        db = SessionLocal()
        try:
            # 1. Setup test users
            u1 = db.query(User).filter(User.email == "verify.complaint1@gmail.com").first()
            if not u1:
                u1 = User(
                    email="verify.complaint1@gmail.com",
                    otp_secret="JBSWY3DPEHPK3PXP",
                    state="Uttar Pradesh",
                    district="PILIBHIT",
                    constituency="PILIBHIT",
                )
                db.add(u1)
                db.commit()
                db.refresh(u1)
            else:
                u1.state = "Uttar Pradesh"
                u1.district = "PILIBHIT"
                u1.constituency = "PILIBHIT"
                db.commit()

            u2 = db.query(User).filter(User.email == "verify.complaint2@gmail.com").first()
            if not u2:
                u2 = User(
                    email="verify.complaint2@gmail.com",
                    otp_secret="JBSWY3DPEHPK3PXP",
                    state="Bihar",
                    district="ARARIA",
                    constituency="ARARIA",
                )
                db.add(u2)
                db.commit()
                db.refresh(u2)

            # Clean previous test complaints
            db.query(Complaint).filter(Complaint.user_id.in_([u1.id, u2.id])).delete(synchronize_session=False)
            db.commit()

            token1 = create_token(sub=str(u1.id), role="user")
            token2 = create_token(sub=str(u2.id), role="user")
            token_auditor = create_token(sub=settings.AUDITOR_ID, role="auditor")

            h1 = {"Authorization": f"Bearer {token1}"}
            h2 = {"Authorization": f"Bearer {token2}"}
            hauditor = {"Authorization": f"Bearer {token_auditor}"}

            def make_image_bytes():
                img = Image.new("RGB", (100, 100), color=(80, 150, 200))
                buf = io.BytesIO()
                img.save(buf, format="JPEG")
                return buf.getvalue()

            valid_jpg = make_image_bytes()

            # Check 1: User with saved location creates complaint and it comes back as pending
            print("\n[CHECK 1] Create complaint with saved location -> pending:")
            res1 = client.post(
                "/complaints",
                headers=h1,
                files={"photo": ("road_issue.jpg", valid_jpg, "image/jpeg")},
                data={"comment": "Broken pipeline causing severe water logging on main road", "lat": 28.63, "lng": 79.80},
            )
            print("Status Code:", res1.status_code)
            c1 = res1.json()
            print("Response:", c1)
            assert res1.status_code == 200
            assert c1["status"] == "pending"
            assert "image_path" not in c1
            c1_id = c1["id"]

            # Check 3A: .txt file renamed to .jpg returns 400
            print("\n[CHECK 3A] .txt file renamed to .jpg -> 400:")
            fake_bytes = b"Hello world, this is a plain text file."
            res_fake = client.post(
                "/complaints",
                headers=h1,
                files={"photo": ("fake.jpg", fake_bytes, "image/jpeg")},
                data={"comment": "Valid comment about streetlight failure"},
            )
            print("Status Code:", res_fake.status_code)
            print("Response:", res_fake.json())
            assert res_fake.status_code == 400

            # Check 3B: Comment shorter than 10 characters returns 400
            print("\n[CHECK 3B] Comment shorter than 10 characters -> 400:")
            res_short = client.post(
                "/complaints",
                headers=h1,
                files={"photo": ("issue.jpg", valid_jpg, "image/jpeg")},
                data={"comment": "Bad road"},
            )
            print("Status Code:", res_short.status_code)
            print("Response:", res_short.json())
            assert res_short.status_code == 400

            # Add complaint 2 and 3 for user 1
            client.post(
                "/complaints",
                headers=h1,
                files={"photo": ("issue2.jpg", valid_jpg, "image/jpeg")},
                data={"comment": "Potholes on school road needing urgent repair"},
            )
            client.post(
                "/complaints",
                headers=h1,
                files={"photo": ("issue3.jpg", valid_jpg, "image/jpeg")},
                data={"comment": "Damaged community hall roofing in village"},
            )

            # Check 2: 4th pending complaint returns 409
            print("\n[CHECK 2] 4th pending complaint -> 409:")
            res4 = client.post(
                "/complaints",
                headers=h1,
                files={"photo": ("issue4.jpg", valid_jpg, "image/jpeg")},
                data={"comment": "Fourth complaint exceeding limit"},
            )
            print("Status Code:", res4.status_code)
            print("Response:", res4.json())
            assert res4.status_code == 409

            # Create complaint for user 2
            res_u2 = client.post(
                "/complaints",
                headers=h2,
                files={"photo": ("u2_pic.jpg", valid_jpg, "image/jpeg")},
                data={"comment": "User 2 complaint about primary health center"},
            )
            assert res_u2.status_code == 200
            u2_c_id = res_u2.json()["id"]

            # Check 4: GET /complaints/mine shows only that user's complaints
            print("\n[CHECK 4] GET /complaints/mine for User 1:")
            mine_res = client.get("/complaints/mine?page=1&page_size=20", headers=h1)
            print("Status Code:", mine_res.status_code)
            mine = mine_res.json()
            print("Total:", mine["total"])
            print("Items count:", len(mine["items"]))
            item_ids = [it["id"] for it in mine["items"]]
            print("Item IDs for User 1:", item_ids)
            assert mine["total"] == 3
            assert c1_id in item_ids
            assert u2_c_id not in item_ids
            print("User 2 complaint ID correctly excluded.")

            # Check 5: Permissions on GET /complaints/{id}/image
            print("\n[CHECK 5] Image access permissions:")
            # Owner
            img_owner = client.get(f"/complaints/{c1_id}/image", headers=h1)
            print("Owner access status:", img_owner.status_code, "Content-Type:", img_owner.headers.get("content-type"))
            assert img_owner.status_code == 200

            # Another user
            img_other = client.get(f"/complaints/{c1_id}/image", headers=h2)
            print("Other user access status:", img_other.status_code, "Response:", img_other.json())
            assert img_other.status_code == 403

            # Auditor
            img_auditor = client.get(f"/complaints/{c1_id}/image", headers=hauditor)
            print("Auditor access status:", img_auditor.status_code, "Content-Type:", img_auditor.headers.get("content-type"))
            assert img_auditor.status_code == 200

            # Unknown ID
            img_unknown = client.get("/complaints/999999/image", headers=h1)
            print("Unknown ID access status:", img_unknown.status_code, "Response:", img_unknown.json())
            assert img_unknown.status_code == 404

            print("\n=== ALL COMPLAINT VERIFICATION CHECKS PASSED ===")
        finally:
            db.close()


if __name__ == "__main__":
    run_verification()
