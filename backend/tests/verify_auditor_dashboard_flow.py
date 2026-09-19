import io
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from PIL import Image

from app.database import SessionLocal
from app.main import app
from app.models import Complaint, User, Submission, Work
from app.security import create_token, settings


def run_verification():
    print("=================================================================")
    print("      AUDITOR DASHBOARD COMPLAINTS FLOW VERIFICATION             ")
    print("=================================================================")
    with TestClient(app) as client:
        db = SessionLocal()
        try:
            # 1. Setup test user
            user = db.query(User).filter(User.email == "dashboard.auditor.user@gmail.com").first()
            if not user:
                user = User(
                    email="dashboard.auditor.user@gmail.com",
                    otp_secret="JBSWY3DPEHPK3PXP",
                    state="Uttar Pradesh",
                    district="PILIBHIT",
                    constituency="PILIBHIT",
                    xp=50,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            else:
                user.state = "Uttar Pradesh"
                user.district = "PILIBHIT"
                user.constituency = "PILIBHIT"
                user.xp = 50
                db.commit()

            # Clean old complaints for this test user
            db.query(Complaint).filter(Complaint.user_id == user.id).delete(synchronize_session=False)
            db.commit()

            user_token = create_token(sub=str(user.id), role="user")
            auditor_token = create_token(sub=settings.AUDITOR_ID, role="auditor")

            h_user = {"Authorization": f"Bearer {user_token}"}
            h_auditor = {"Authorization": f"Bearer {auditor_token}"}

            def make_image_bytes():
                img = Image.new("RGB", (100, 100), color=(80, 160, 240))
                buf = io.BytesIO()
                img.save(buf, format="JPEG")
                return buf.getvalue()

            img_bytes = make_image_bytes()

            # Create complaint 1 (to be accepted)
            res1 = client.post(
                "/complaints",
                headers=h_user,
                files={"photo": ("c1.jpg", img_bytes, "image/jpeg")},
                data={"comment": "Damaged streetlight near community center"},
            )
            assert res1.status_code == 200
            c1_id = res1.json()["id"]

            # Create complaint 2 (to be rejected)
            res2 = client.post(
                "/complaints",
                headers=h_user,
                files={"photo": ("c2.jpg", img_bytes, "image/jpeg")},
                data={"comment": "Tree branches touching transmission lines"},
            )
            assert res2.status_code == 200
            c2_id = res2.json()["id"]

            print(f"\n[1] Initial State: User XP = {user.xp}")
            print(f"    Complaint 1 (ID {c1_id}): Pending")
            print(f"    Complaint 2 (ID {c2_id}): Pending")

            # Check Complaints list as auditor
            print("\n[2] Auditor retrieves pending complaints (GET /auditor/complaints?status=pending):")
            res_aud_pending = client.get("/auditor/complaints?status=pending&page=1&page_size=20", headers=h_auditor)
            assert res_aud_pending.status_code == 200
            pending_items = res_aud_pending.json()["items"]
            pending_ids = [it["id"] for it in pending_items]
            print(f"    Found {len(pending_items)} pending complaints: {pending_ids}")
            assert c1_id in pending_ids
            assert c2_id in pending_ids

            # Test Accept
            print("\n[3] Auditor accepts Complaint 1 with comment:")
            accept_payload = {"comment": "Work order issued to electrical maintenance division."}
            res_accept = client.post(f"/auditor/complaints/{c1_id}/accept", headers=h_auditor, json=accept_payload)
            print(f"    POST /auditor/complaints/{c1_id}/accept -> Status: {res_accept.status_code}")
            assert res_accept.status_code == 200

            db.refresh(user)
            print(f"    User XP after accept: {user.xp} (increased by exactly {user.xp - 50})")
            assert user.xp == 100, f"Expected 100, got {user.xp}"

            # Check duplicate accept (rapid tap protection server-side)
            print("\n[4] Duplicate accept test (rapid tap protection):")
            res_dup_accept = client.post(f"/auditor/complaints/{c1_id}/accept", headers=h_auditor, json=accept_payload)
            print(f"    Second accept call -> Status: {res_dup_accept.status_code} ({res_dup_accept.json()})")
            assert res_dup_accept.status_code == 409
            db.refresh(user)
            assert user.xp == 100, "XP must not change on duplicate accept"

            # Check citizen view of Complaint 1
            print("\n[5] Citizen view on GET /complaints/mine:")
            mine_res1 = client.get("/complaints/mine", headers=h_user)
            c1_mine = next(it for it in mine_res1.json()["items"] if it["id"] == c1_id)
            print(f"    Complaint 1 Status: {c1_mine['status']}")
            print(f"    Complaint 1 Auditor Comment: {c1_mine['auditor_comment']}")
            print(f"    Complaint 1 XP Awarded: {c1_mine['xp_awarded']}")
            assert c1_mine["status"] == "accepted"
            assert c1_mine["auditor_comment"] == accept_payload["comment"]
            assert c1_mine["xp_awarded"] == 50

            # Test Reject
            print("\n[6] Auditor rejects Complaint 2 with comment:")
            reject_payload = {"comment": "Jurisdiction belongs to state electricity board, forwarded accordingly."}
            res_reject = client.post(f"/auditor/complaints/{c2_id}/reject", headers=h_auditor, json=reject_payload)
            print(f"    POST /auditor/complaints/{c2_id}/reject -> Status: {res_reject.status_code}")
            assert res_reject.status_code == 200

            db.refresh(user)
            print(f"    User XP after reject: {user.xp} (unchanged at 100)")
            assert user.xp == 100, "Reject must award 0 XP"

            # Check citizen view of Complaint 2
            mine_res2 = client.get("/complaints/mine", headers=h_user)
            c2_mine = next(it for it in mine_res2.json()["items"] if it["id"] == c2_id)
            print(f"    Complaint 2 Status: {c2_mine['status']}")
            print(f"    Complaint 2 Auditor Comment: {c2_mine['auditor_comment']}")
            print(f"    Complaint 2 XP Awarded: {c2_mine['xp_awarded']}")
            assert c2_mine["status"] == "rejected"
            assert c2_mine["auditor_comment"] == reject_payload["comment"]
            assert c2_mine["xp_awarded"] == 0

            # Test that "Photo checks" (GET /auditor/submissions) is completely untouched and functioning
            print("\n[7] Verify 'Photo checks' (submissions) continues to work:")
            res_subs = client.get("/auditor/submissions?status=pending", headers=h_auditor)
            print(f"    GET /auditor/submissions?status=pending -> Status: {res_subs.status_code}")
            assert res_subs.status_code == 200

            print("\n=================================================================")
            print("        AUDITOR DASHBOARD COMPLAINTS FLOW VERIFIED!              ")
            print("=================================================================")
        finally:
            db.close()


if __name__ == "__main__":
    run_verification()
