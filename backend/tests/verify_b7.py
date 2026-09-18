import io
from pathlib import Path
from fastapi.testclient import TestClient
from PIL import Image

from app.database import SessionLocal
from app.main import app
from app.models import Submission, User, Work
from app.security import create_token


def run_tests():
    client = TestClient(app)
    db = SessionLocal()
    try:
        # Setup test user in Pilibhit, UP
        test_user = (
            db.query(User).filter(User.email == "uploader.b7@gmail.com").first()
        )
        if not test_user:
            test_user = User(
                email="uploader.b7@gmail.com",
                otp_secret="JBSWY3DPEHPK3PXP",
                state="Uttar Pradesh",
                district="PILIBHIT",
                constituency="PILIBHIT",
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
        else:
            test_user.state = "Uttar Pradesh"
            test_user.district = "PILIBHIT"
            test_user.constituency = "PILIBHIT"
            db.commit()

        token = create_token(sub=str(test_user.id), role="user")
        headers = {"Authorization": f"Bearer {token}"}

        # Find a valid matching work for this user
        matching_work = (
            db.query(Work)
            .filter(
                Work.source == "LS",
                Work.state_norm == "UTTAR PRADESH",
                Work.district_norm == "PILIBHIT",
                Work.constituency_norm == "PILIBHIT",
            )
            .first()
        )
        assert matching_work is not None, "No matching work found for test"
        work_id = matching_work.id

        # Clean up any existing submissions for this test user and work
        db.query(Submission).filter(
            Submission.user_id == test_user.id, Submission.work_id == work_id
        ).delete()
        db.commit()

        print("=== Test 1: A .txt file renamed to .jpg is rejected with 400 ===")
        fake_jpg_content = b"This is a text file trying to disguise as an image."
        files = {"photo": ("disguised_file.jpg", fake_jpg_content, "image/jpeg")}
        res_fake = client.post(
            f"/works/{work_id}/submissions", headers=headers, files=files
        )
        print("Status:", res_fake.status_code, "| Detail:", res_fake.json())
        assert res_fake.status_code == 400
        assert "not a valid image" in res_fake.json()["detail"].lower()

        print("\n=== Test 2: Valid image upload returns pending submission ===")
        # Create a real JPEG image in memory with Pillow
        img = Image.new("RGB", (200, 200), color=(34, 139, 34))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        valid_jpeg_content = img_bytes.getvalue()

        files = {"photo": ("real_camera_pic.jpg", valid_jpeg_content, "image/jpeg")}
        data = {"lat": 28.63, "lng": 79.80}
        res_valid = client.post(
            f"/works/{work_id}/submissions",
            headers=headers,
            files=files,
            data=data,
        )
        print("Status:", res_valid.status_code)
        sub_data = res_valid.json()
        print("Submission returned:", sub_data)
        assert res_valid.status_code == 200
        assert sub_data["status"] == "pending"
        assert sub_data["work_id"] == work_id
        assert sub_data["user_id"] == test_user.id
        assert sub_data["image_path"].startswith("uploads/")
        assert sub_data["lat"] == 28.63

        # Verify file exists on disk with UUID filename
        saved_file = Path(__file__).resolve().parent.parent / sub_data["image_path"]
        assert saved_file.is_file(), f"File was not saved at {saved_file}"
        print(f"Saved file confirmed on disk: {saved_file.name}")

        print("\n=== Test 3: Second upload for the same work returns 409 ===")
        res_second = client.post(
            f"/works/{work_id}/submissions",
            headers=headers,
            files={"photo": ("second_pic.jpg", valid_jpeg_content, "image/jpeg")},
        )
        print("Status:", res_second.status_code, "| Detail:", res_second.json())
        assert res_second.status_code == 409
        assert "pending" in res_second.json()["detail"].lower()

        print("\n=== Test 4: Work in different location returns 403 ===")
        other_work = (
            db.query(Work)
            .filter(Work.state_norm == "BIHAR", Work.district_norm == "ARARIA")
            .first()
        )
        assert other_work is not None
        res_403 = client.post(
            f"/works/{other_work.id}/submissions",
            headers=headers,
            files={"photo": ("pic.jpg", valid_jpeg_content, "image/jpeg")},
        )
        print("Status on wrong location:", res_403.status_code, "| Detail:", res_403.json())
        assert res_403.status_code == 403

        print("\n=== Test 5: Uploads folder is NOT served as static files ===")
        res_static = client.get(f"/{sub_data['image_path']}")
        print("GET /uploads/... status:", res_static.status_code)
        assert res_static.status_code == 404

        print("\nALL STEP B7 CHECKS PASSED!")
    finally:
        db.close()


if __name__ == "__main__":
    run_tests()
