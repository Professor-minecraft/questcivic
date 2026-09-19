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
    print("=================================================================")
    print("        PROFILE COMPLAINTS SECTION DATA VERIFICATION             ")
    print("=================================================================")
    with TestClient(app) as client:
        db = SessionLocal()
        try:
            # 1. Setup test user
            user = db.query(User).filter(User.email == "profile.test.user@gmail.com").first()
            if not user:
                user = User(
                    email="profile.test.user@gmail.com",
                    otp_secret="JBSWY3DPEHPK3PXP",
                    state="Uttar Pradesh",
                    district="PILIBHIT",
                    constituency="PILIBHIT",
                    xp=200,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            else:
                user.state = "Uttar Pradesh"
                user.district = "PILIBHIT"
                user.constituency = "PILIBHIT"
                user.xp = 200
                db.commit()

            # Clean old complaints for this test user
            db.query(Complaint).filter(Complaint.user_id == user.id).delete(synchronize_session=False)
            db.commit()

            user_token = create_token(sub=str(user.id), role="user")
            auditor_token = create_token(sub=settings.AUDITOR_ID, role="auditor")

            h_user = {"Authorization": f"Bearer {user_token}"}
            h_auditor = {"Authorization": f"Bearer {auditor_token}"}

            def make_image_bytes():
                img = Image.new("RGB", (120, 120), color=(70, 140, 210))
                buf = io.BytesIO()
                img.save(buf, format="JPEG")
                return buf.getvalue()

            img_bytes = make_image_bytes()

            # Create Complaint 1: Will be accepted
            res1 = client.post(
                "/complaints",
                headers=h_user,
                files={"photo": ("c1.jpg", img_bytes, "image/jpeg")},
                data={"comment": "Broken street lighting creating safety issue at crossroads"},
            )
            assert res1.status_code == 200, res1.text
            c1_id = res1.json()["id"]

            # Create Complaint 2: Will be rejected
            res2 = client.post(
                "/complaints",
                headers=h_user,
                files={"photo": ("c2.jpg", img_bytes, "image/jpeg")},
                data={"comment": "Private property wall damage reported in error"},
            )
            assert res2.status_code == 200, res2.text
            c2_id = res2.json()["id"]

            # Create Complaint 3: Will stay pending
            res3 = client.post(
                "/complaints",
                headers=h_user,
                files={"photo": ("c3.jpg", img_bytes, "image/jpeg")},
                data={"comment": "Waterlogging due to blocked culvert under railway crossing"},
            )
            assert res3.status_code == 200, res3.text
            c3_id = res3.json()["id"]

            # Auditor accepts Complaint 1
            accept_res = client.post(
                f"/auditor/complaints/{c1_id}/accept",
                headers=h_auditor,
                json={"comment": "Verified by inspection team. Municipal work order issued."},
            )
            assert accept_res.status_code == 200, accept_res.text

            # Auditor rejects Complaint 2
            reject_res = client.post(
                f"/auditor/complaints/{c2_id}/reject",
                headers=h_auditor,
                json={"comment": "Damage is on private residential property, outside MPLADS scope."},
            )
            assert reject_res.status_code == 200, reject_res.text

            # Complaint 3 remains pending

            # Now test GET /complaints/mine as citizen
            print("\n[TEST] GET /complaints/mine for Profile page:")
            mine_res = client.get("/complaints/mine?page=1&page_size=20", headers=h_user)
            assert mine_res.status_code == 200
            data = mine_res.json()
            items = data["items"]
            print(f"Total Complaints: {data['total']}, Retrieved: {len(items)}")

            # Verify all 3 are present
            accepted_item = next(it for it in items if it["id"] == c1_id)
            rejected_item = next(it for it in items if it["id"] == c2_id)
            pending_item = next(it for it in items if it["id"] == c3_id)

            print("\n1. Accepted Complaint:")
            print(f"   Status: {accepted_item['status']}")
            print(f"   Auditor Comment: {accepted_item['auditor_comment']}")
            print(f"   XP Awarded: {accepted_item['xp_awarded']}")
            assert accepted_item["status"] == "accepted"
            assert accepted_item["auditor_comment"] == "Verified by inspection team. Municipal work order issued."
            assert accepted_item["xp_awarded"] == 50

            print("\n2. Rejected Complaint:")
            print(f"   Status: {rejected_item['status']}")
            print(f"   Auditor Comment: {rejected_item['auditor_comment']}")
            print(f"   XP Awarded: {rejected_item['xp_awarded']}")
            assert rejected_item["status"] == "rejected"
            assert rejected_item["auditor_comment"] == "Damage is on private residential property, outside MPLADS scope."
            assert rejected_item["xp_awarded"] == 0

            print("\n3. Pending Complaint:")
            print(f"   Status: {pending_item['status']}")
            print(f"   Auditor Comment: {pending_item['auditor_comment']}")
            print(f"   XP Awarded: {pending_item['xp_awarded']}")
            assert pending_item["status"] == "pending"
            assert pending_item["auditor_comment"] is None
            assert pending_item["xp_awarded"] == 0

            # Test image retrieval for each (as blob)
            print("\n[TEST] Image endpoints for thumbnail display:")
            for cid in [c1_id, c2_id, c3_id]:
                img_res = client.get(f"/complaints/{cid}/image", headers=h_user)
                assert img_res.status_code == 200
                assert len(img_res.content) > 0
                print(f"   Complaint {cid} image loaded successfully ({len(img_res.content)} bytes, Content-Type: {img_res.headers.get('content-type')})")

            print("\n=================================================================")
            print("        ALL PROFILE COMPLAINTS VERIFICATIONS PASSED!             ")
            print("=================================================================")
        finally:
            db.close()


if __name__ == "__main__":
    run_verification()
