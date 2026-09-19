import io
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from PIL import Image

from app.database import SessionLocal
from app.main import app
from app.models import Complaint, User, XPLog
from app.security import create_token, settings


def run_verification():
    print("=================================================================")
    print("           AUDITOR COMPLAINTS ENDPOINTS VERIFICATION             ")
    print("=================================================================")
    with TestClient(app) as client:
        db = SessionLocal()
        try:
            # 1. Setup test user
            user = db.query(User).filter(User.email == "verify.auditor.user@gmail.com").first()
            if not user:
                user = User(
                    email="verify.auditor.user@gmail.com",
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

            # Clean old test complaints
            db.query(Complaint).filter(Complaint.user_id == user.id).delete(synchronize_session=False)
            db.commit()

            user_token = create_token(sub=str(user.id), role="user")
            auditor_token = create_token(sub=settings.AUDITOR_ID, role="auditor")

            h_user = {"Authorization": f"Bearer {user_token}"}
            h_auditor = {"Authorization": f"Bearer {auditor_token}"}

            def make_image_bytes():
                img = Image.new("RGB", (100, 100), color=(60, 120, 180))
                buf = io.BytesIO()
                img.save(buf, format="JPEG")
                return buf.getvalue()

            img_bytes = make_image_bytes()

            # Create 2 pending complaints
            c1_res = client.post(
                "/complaints",
                headers=h_user,
                files={"photo": ("c1.jpg", img_bytes, "image/jpeg")},
                data={"comment": "Damaged drainage pipeline flooding residential area"},
            )
            c1_id = c1_res.json()["id"]

            c2_res = client.post(
                "/complaints",
                headers=h_user,
                files={"photo": ("c2.jpg", img_bytes, "image/jpeg")},
                data={"comment": "Hazardous low hanging high-voltage electrical cable"},
            )
            c2_id = c2_res.json()["id"]

            print(f"\n[SETUP] Created 2 pending complaints for user {user.email}:")
            print(f"  - Complaint 1 ID: {c1_id} (Status: pending)")
            print(f"  - Complaint 2 ID: {c2_id} (Status: pending)")
            print(f"  - User Initial XP: {user.xp}")

            # -------------------------------------------------------------
            # REQUIREMENT: A user token gets 403 on all /auditor/complaints routes
            # -------------------------------------------------------------
            print("\n-------------------------------------------------------------")
            print("[CHECK 1] User token receives 403 on all /auditor/complaints routes:")
            print("-------------------------------------------------------------")
            res_u_get = client.get("/auditor/complaints", headers=h_user)
            print(f"GET /auditor/complaints -> Status: {res_u_get.status_code}, Response: {res_u_get.json()}")
            assert res_u_get.status_code == 403

            res_u_acc = client.post(f"/auditor/complaints/{c1_id}/accept", headers=h_user, json={"comment": "Auditor accept note"})
            print(f"POST /auditor/complaints/{c1_id}/accept -> Status: {res_u_acc.status_code}, Response: {res_u_acc.json()}")
            assert res_u_acc.status_code == 403

            res_u_rej = client.post(f"/auditor/complaints/{c2_id}/reject", headers=h_user, json={"comment": "Auditor reject note"})
            print(f"POST /auditor/complaints/{c2_id}/reject -> Status: {res_u_rej.status_code}, Response: {res_u_rej.json()}")
            assert res_u_rej.status_code == 403

            # -------------------------------------------------------------
            # REQUIREMENT: GET /auditor/complaints pagination, fields, newest first
            # -------------------------------------------------------------
            print("\n-------------------------------------------------------------")
            print("[CHECK 2] GET /auditor/complaints (Auditor token):")
            print("-------------------------------------------------------------")
            res_aud_list = client.get("/auditor/complaints?status=pending&page=1&page_size=20", headers=h_auditor)
            print(f"Status Code: {res_aud_list.status_code}")
            list_data = res_aud_list.json()
            print(f"Total: {list_data['total']}, Page: {list_data['page']}, Page Size: {list_data['page_size']}")
            for item in list_data["items"]:
                print(f"  Item: ID={item['id']}, user_email={item['user_email']}, status={item['status']}, xp_awarded={item['xp_awarded']}, state={item['state']}, comment={item['comment'][:35]}...")
                assert "image_path" not in item, "image_path must NEVER be included in auditor complaints list"
            assert res_aud_list.status_code == 200

            # -------------------------------------------------------------
            # REQUIREMENT: Accepting a pending complaint raises that user's xp
            # by exactly 50, and GET /complaints/mine shows status accepted,
            # the auditor_comment and xp_awarded 50.
            # -------------------------------------------------------------
            print("\n-------------------------------------------------------------")
            print("[CHECK 3] Auditor accepts pending complaint:")
            print("-------------------------------------------------------------")
            db.refresh(user)
            xp_before_accept = user.xp
            print(f"User XP Before Accept: {xp_before_accept}")

            accept_payload = {"comment": "Drainage inspection completed. Repair scheduled by local municipality."}
            res_acc = client.post(f"/auditor/complaints/{c1_id}/accept", headers=h_auditor, json=accept_payload)
            print(f"POST /auditor/complaints/{c1_id}/accept -> Status: {res_acc.status_code}")
            print(f"Response Body: {res_acc.json()}")
            assert res_acc.status_code == 200

            db.refresh(user)
            xp_after_accept = user.xp
            print(f"User XP After Accept: {xp_after_accept} (Diff: +{xp_after_accept - xp_before_accept})")
            assert xp_after_accept == xp_before_accept + 50, "User XP must increase by exactly 50"

            res_mine = client.get("/complaints/mine?page=1&page_size=20", headers=h_user)
            print(f"GET /complaints/mine -> Status: {res_mine.status_code}")
            mine_c1 = next(it for it in res_mine.json()["items"] if it["id"] == c1_id)
            print(f"Citizen View of Complaint {c1_id}:")
            print(f"  status: {mine_c1['status']}")
            print(f"  auditor_comment: {mine_c1['auditor_comment']}")
            print(f"  xp_awarded: {mine_c1['xp_awarded']}")
            assert mine_c1["status"] == "accepted"
            assert mine_c1["auditor_comment"] == accept_payload["comment"]
            assert mine_c1["xp_awarded"] == 50

            # -------------------------------------------------------------
            # REQUIREMENT: Accepting the same complaint again returns 409 and XP does not change
            # -------------------------------------------------------------
            print("\n-------------------------------------------------------------")
            print("[CHECK 4] Accepting same complaint again -> 409 & XP unchanged:")
            print("-------------------------------------------------------------")
            res_acc_dup = client.post(f"/auditor/complaints/{c1_id}/accept", headers=h_auditor, json={"comment": "Trying duplicate accept"})
            print(f"POST /auditor/complaints/{c1_id}/accept (duplicate) -> Status: {res_acc_dup.status_code}, Response: {res_acc_dup.json()}")
            assert res_acc_dup.status_code == 409

            db.refresh(user)
            print(f"User XP After Duplicate Attempt: {user.xp} (Unchanged: {user.xp == xp_after_accept})")
            assert user.xp == xp_after_accept

            # -------------------------------------------------------------
            # REQUIREMENT: Rejecting a pending complaint gives no XP and shows
            # the auditor_comment to the user
            # -------------------------------------------------------------
            print("\n-------------------------------------------------------------")
            print("[CHECK 5] Auditor rejects pending complaint (gives no XP):")
            print("-------------------------------------------------------------")
            db.refresh(user)
            xp_before_reject = user.xp
            print(f"User XP Before Reject: {xp_before_reject}")

            reject_payload = {"comment": "Location falls outside project jurisdiction. Transferred to power corporation."}
            res_rej = client.post(f"/auditor/complaints/{c2_id}/reject", headers=h_auditor, json=reject_payload)
            print(f"POST /auditor/complaints/{c2_id}/reject -> Status: {res_rej.status_code}")
            print(f"Response Body: {res_rej.json()}")
            assert res_rej.status_code == 200

            db.refresh(user)
            xp_after_reject = user.xp
            print(f"User XP After Reject: {xp_after_reject} (Diff: +{xp_after_reject - xp_before_reject})")
            assert xp_after_reject == xp_before_reject, "Reject must award NO XP"

            res_mine_rej = client.get("/complaints/mine?page=1&page_size=20", headers=h_user)
            mine_c2 = next(it for it in res_mine_rej.json()["items"] if it["id"] == c2_id)
            print(f"Citizen View of Complaint {c2_id}:")
            print(f"  status: {mine_c2['status']}")
            print(f"  auditor_comment: {mine_c2['auditor_comment']}")
            print(f"  xp_awarded: {mine_c2['xp_awarded']}")
            assert mine_c2["status"] == "rejected"
            assert mine_c2["auditor_comment"] == reject_payload["comment"]
            assert mine_c2["xp_awarded"] == 0

            # -------------------------------------------------------------
            # REQUIREMENT: Rejecting same complaint again returns 409
            # -------------------------------------------------------------
            print("\n-------------------------------------------------------------")
            print("[CHECK 6] Rejecting non-pending complaint -> 409:")
            print("-------------------------------------------------------------")
            res_rej_dup = client.post(f"/auditor/complaints/{c2_id}/reject", headers=h_auditor, json={"comment": "Trying duplicate reject"})
            print(f"POST /auditor/complaints/{c2_id}/reject (duplicate) -> Status: {res_rej_dup.status_code}, Response: {res_rej_dup.json()}")
            assert res_rej_dup.status_code == 409

            # -------------------------------------------------------------
            # REQUIREMENT: Validation (Unknown id -> 404, comment length / missing -> 400 or 422)
            # -------------------------------------------------------------
            print("\n-------------------------------------------------------------")
            print("[CHECK 7] Validation tests (404 and 400/422):")
            print("-------------------------------------------------------------")
            res_unknown = client.post("/auditor/complaints/999999/accept", headers=h_auditor, json={"comment": "Valid comment length"})
            print(f"POST /auditor/complaints/999999/accept -> Status: {res_unknown.status_code}, Response: {res_unknown.json()}")
            assert res_unknown.status_code == 404

            res_short = client.post(f"/auditor/complaints/{c1_id}/accept", headers=h_auditor, json={"comment": "ab"})
            print(f"POST too short comment ('ab') -> Status: {res_short.status_code}")
            assert res_short.status_code in [400, 422]

            res_empty = client.post(f"/auditor/complaints/{c1_id}/accept", headers=h_auditor, json={})
            print(f"POST missing comment -> Status: {res_empty.status_code}")
            assert res_empty.status_code in [400, 422]

            print("\n=============================================================")
            print("         ALL AUDITOR COMPLAINTS CHECKS PASSED!               ")
            print("=============================================================")
        finally:
            db.close()


if __name__ == "__main__":
    run_verification()
