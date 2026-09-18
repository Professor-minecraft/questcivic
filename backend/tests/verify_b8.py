import io
from pathlib import Path
from fastapi.testclient import TestClient
from PIL import Image

from app.database import SessionLocal
from app.main import app
from app.models import Submission, User, Work, XPLog
from app.security import create_token


def run_tests():
    client = TestClient(app)
    db = SessionLocal()
    try:
        # 1. Setup a test citizen user
        user = db.query(User).filter(User.email == "citizen.b8@gmail.com").first()
        if not user:
            user = User(
                email="citizen.b8@gmail.com",
                otp_secret="JBSWY3DPEHPK3PXP",
                state="Uttar Pradesh",
                district="PILIBHIT",
                constituency="PILIBHIT",
                xp=0,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.xp = 0
            user.state = "Uttar Pradesh"
            user.district = "PILIBHIT"
            user.constituency = "PILIBHIT"
            db.commit()

        user_token = create_token(sub=str(user.id), role="user")
        user_headers = {"Authorization": f"Bearer {user_token}"}
        auditor_token = create_token(sub="auditor", role="auditor")
        auditor_headers = {"Authorization": f"Bearer {auditor_token}"}

        # 2. Find a matching work
        work = (
            db.query(Work)
            .filter(
                Work.source == "LS",
                Work.state_norm == "UTTAR PRADESH",
                Work.district_norm == "PILIBHIT",
            )
            .first()
        )
        assert work is not None, "Work not found"

        # 3. Create a real image on disk and insert a pending submission
        uploads_dir = Path(__file__).resolve().parent.parent / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        img_name = "test_b8_image.jpg"
        img_path = uploads_dir / img_name
        img = Image.new("RGB", (150, 150), color=(200, 50, 50))
        img.save(img_path, format="JPEG")

        # Clean old test submissions for this work and user
        db.query(Submission).filter(
            Submission.user_id == user.id, Submission.work_id == work.id
        ).delete()
        db.commit()

        submission = Submission(
            user_id=user.id,
            work_id=work.id,
            image_path=f"uploads/{img_name}",
            status="pending",
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)
        sub_id = submission.id

        print("=== Test 1: GET /auditor/submissions returns pending submission with details ===")
        res_list = client.get("/auditor/submissions?status=pending", headers=auditor_headers)
        print("Status:", res_list.status_code)
        assert res_list.status_code == 200
        subs = res_list.json()
        target_sub = next((s for s in subs if s["id"] == sub_id), None)
        assert target_sub is not None, "Submitted work not in pending list"
        print("Found submission in auditor list:")
        print(f"  - User email: {target_sub['user_email']}")
        print(f"  - Work Description: {target_sub['work']['description'][:50]}...")
        print(f"  - MP: {target_sub['work']['mp_name']}")
        print(f"  - District: {target_sub['work']['district']}")
        assert target_sub["user_email"] == "citizen.b8@gmail.com"

        print("\n=== Test 2: User token CANNOT open image URL (403 Forbidden) ===")
        res_user_img = client.get(
            f"/auditor/submissions/{sub_id}/image", headers=user_headers
        )
        print("User image request status:", res_user_img.status_code, "| Detail:", res_user_img.json())
        assert res_user_img.status_code == 403

        print("\n=== Test 3: Auditor token opens image URL successfully (200 OK) ===")
        res_auditor_img = client.get(
            f"/auditor/submissions/{sub_id}/image", headers=auditor_headers
        )
        print("Auditor image request status:", res_auditor_img.status_code)
        assert res_auditor_img.status_code == 200
        assert len(res_auditor_img.content) > 0

        print("\n=== Test 4: Approving pending submission raises XP by exactly 150 ===")
        db.refresh(user)
        initial_xp = user.xp
        print(f"Initial user XP: {initial_xp}")

        res_approve = client.post(
            f"/auditor/submissions/{sub_id}/approve", headers=auditor_headers
        )
        print("Approve status:", res_approve.status_code)
        assert res_approve.status_code == 200
        assert res_approve.json()["status"] == "approved"

        db.refresh(user)
        final_xp = user.xp
        print(f"User XP after approval: {final_xp}")
        assert final_xp == initial_xp + 150, f"XP was expected to be {initial_xp + 150}, got {final_xp}"

        # Verify xp_log row was inserted
        xp_entry = db.query(XPLog).filter(XPLog.submission_id == sub_id).first()
        assert xp_entry is not None, "XPLog entry not created"
        assert xp_entry.points == 150
        print(f"Verified XP log entry created with {xp_entry.points} points.")

        print("\n=== Test 5: Approving the same submission again returns 409 and XP does not change ===")
        res_approve_again = client.post(
            f"/auditor/submissions/{sub_id}/approve", headers=auditor_headers
        )
        print("Second approval status:", res_approve_again.status_code, "| Detail:", res_approve_again.json())
        assert res_approve_again.status_code == 409

        db.refresh(user)
        assert user.xp == final_xp, "User XP changed on duplicate approval!"
        print(f"Confirmed User XP remained unchanged at {user.xp}.")

        print("\n=== Test 6: Rejection test ===")
        # Create another submission to test reject
        sub_reject = Submission(
            user_id=user.id,
            work_id=work.id,
            image_path=f"uploads/{img_name}",
            status="pending",
        )
        db.add(sub_reject)
        db.commit()
        db.refresh(sub_reject)

        res_reject = client.post(
            f"/auditor/submissions/{sub_reject.id}/reject",
            headers=auditor_headers,
            json={"reason": "Photo is blurry and does not show completed work"},
        )
        print("Reject status:", res_reject.status_code)
        assert res_reject.status_code == 200
        assert res_reject.json()["status"] == "rejected"
        assert res_reject.json()["reject_reason"] == "Photo is blurry and does not show completed work"

        db.refresh(user)
        assert user.xp == final_xp, "XP should not change on rejection"
        print(f"Confirmed rejection saved reason and user XP remained at {user.xp}.")

        print("\nALL STEP B8 CHECKS PASSED!")
    finally:
        # Cleanup test image
        if img_path.is_file():
            img_path.unlink()
        db.close()


if __name__ == "__main__":
    run_tests()
