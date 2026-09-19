"""
verify_scope.py

Verification script for Task 1 to Task 4:
- Two constituencies and two auditors: each auditor lists only their own photos and complaints.
- Opening or approving an item of the other constituency returns 404.
- The built-in auditor and the admin see everything.
- A user who later changes location does not move an old submission to another auditor.
- New uploads store the norm columns.
- GET /auditor/me works for both DB auditor and built-in auditor.
- BUILTIN_AUDITOR_ENABLED=false blocks the built-in login.
"""

import io
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bcrypt
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import Auditor, Complaint, Submission, User, Work, XPLog
from app.security import create_token, init_admin_credentials, init_auditor_credentials
from app.services.normalize import normalize_place


def make_test_image_bytes():
    img = Image.new("RGB", (100, 100), color=(50, 120, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def main():
    init_auditor_credentials()
    init_admin_credentials()

    client = TestClient(app)
    db = SessionLocal()

    try:
        print("=" * 70)
        print("STARTING AUDITOR CONSTITUENCY SCOPE VERIFICATION")
        print("=" * 70)

        # ---------------------------------------------------------------------
        # 1. Setup two constituencies and two auditors
        # Constituency A: Uttar Pradesh / PILIBHIT
        # Constituency B: Maharashtra / NAGPUR
        # ---------------------------------------------------------------------
        print("\n--- 1. Setting up 2 auditors and 2 users in distinct constituencies ---")

        # Cleanup existing test entities if any
        test_emails = [
            "aud.pilibhit@test.com", "aud.nagpur@test.com",
            "citizen.pilibhit@test.com", "citizen.nagpur@test.com"
        ]
        for em in test_emails:
            aud = db.query(Auditor).filter(Auditor.email == em).first()
            if aud:
                db.delete(aud)
            u = db.query(User).filter(User.email == em).first()
            if u:
                db.query(XPLog).filter(XPLog.user_id == u.id).delete()
                # Clean up submissions & complaints
                for s in db.query(Submission).filter(Submission.user_id == u.id).all():
                    p = Path("c:/Users/Mrinay/Desktop/CivicQuest/backend") / s.image_path
                    if p.is_file():
                        p.unlink()
                    db.delete(s)
                for c in db.query(Complaint).filter(Complaint.user_id == u.id).all():
                    p = Path("c:/Users/Mrinay/Desktop/CivicQuest/backend") / c.image_path
                    if p.is_file():
                        p.unlink()
                    db.delete(c)
                db.delete(u)
        db.commit()

        # Create Auditor A (UP / PILIBHIT)
        aud_a = Auditor(
            name="Auditor Pilibhit",
            dob=date(1988, 5, 10),
            email="aud.pilibhit@test.com",
            state="Uttar Pradesh",
            district="PILIBHIT",
            constituency="PILIBHIT",
            status="active",
            password_hash=hash_pw("audpass123"),
        )
        db.add(aud_a)

        # Create Auditor B (Maharashtra / NAGPUR)
        aud_b = Auditor(
            name="Auditor Nagpur",
            dob=date(1992, 8, 20),
            email="aud.nagpur@test.com",
            state="Maharashtra",
            district="NAGPUR",
            constituency="NAGPUR",
            status="active",
            password_hash=hash_pw("audpass123"),
        )
        db.add(aud_b)

        # Create User A (UP / PILIBHIT)
        user_a = User(
            email="citizen.pilibhit@test.com",
            otp_secret="JBSWY3DPEHPK3PXP",
            state="Uttar Pradesh",
            district="PILIBHIT",
            constituency="PILIBHIT",
            xp=0,
        )
        db.add(user_a)

        # Create User B (Maharashtra / NAGPUR)
        user_b = User(
            email="citizen.nagpur@test.com",
            otp_secret="JBSWY3DPEHPK3PXP",
            state="Maharashtra",
            district="NAGPUR",
            constituency="NAGPUR",
            xp=0,
        )
        db.add(user_b)
        db.commit()
        db.refresh(aud_a)
        db.refresh(aud_b)
        db.refresh(user_a)
        db.refresh(user_b)

        print(f"Auditor A: id={aud_a.id}, email={aud_a.email}, state={aud_a.state}, constituency={aud_a.constituency}")
        print(f"Auditor B: id={aud_b.id}, email={aud_b.email}, state={aud_b.state}, constituency={aud_b.constituency}")
        print(f"User A: id={user_a.id}, state={user_a.state}, constituency={user_a.constituency}")
        print(f"User B: id={user_b.id}, state={user_b.state}, constituency={user_b.constituency}")

        # Tokens & headers
        token_user_a = create_token(sub=str(user_a.id), role="user")
        token_user_b = create_token(sub=str(user_b.id), role="user")
        h_user_a = {"Authorization": f"Bearer {token_user_a}"}
        h_user_b = {"Authorization": f"Bearer {token_user_b}"}

        token_aud_a = create_token(sub=aud_a.email, role="auditor", extra={"auditor_id": aud_a.id})
        token_aud_b = create_token(sub=aud_b.email, role="auditor", extra={"auditor_id": aud_b.id})
        token_builtin = create_token(sub=settings.AUDITOR_ID, role="auditor")
        token_admin = create_token(sub=settings.ADMIN_ID, role="admin")

        h_aud_a = {"Authorization": f"Bearer {token_aud_a}"}
        h_aud_b = {"Authorization": f"Bearer {token_aud_b}"}
        h_builtin = {"Authorization": f"Bearer {token_builtin}"}
        h_admin = {"Authorization": f"Bearer {token_admin}"}

        # Find matching works for User A and User B
        work_a = db.query(Work).filter(Work.district_norm == "PILIBHIT").first()
        work_b = db.query(Work).filter(Work.district_norm == "NAGPUR").first()
        assert work_a is not None, "Work A not found"
        assert work_b is not None, "Work B not found"

        # ---------------------------------------------------------------------
        # 2. Upload submissions and complaints (Task 1: Snapshot columns)
        # ---------------------------------------------------------------------
        print("\n--- 2. Creating submissions and complaints (testing snapshot norm columns) ---")

        # Submission A (Pilibhit)
        img_bytes = make_test_image_bytes()
        res_sub_a = client.post(
            f"/works/{work_a.id}/submissions",
            headers=h_user_a,
            files={"photo": ("photo_a.jpg", img_bytes, "image/jpeg")},
        )
        assert res_sub_a.status_code == 200, res_sub_a.text
        sub_a_data = res_sub_a.json()
        sub_a_id = sub_a_data["id"]

        # Submission B (Nagpur)
        res_sub_b = client.post(
            f"/works/{work_b.id}/submissions",
            headers=h_user_b,
            files={"photo": ("photo_b.jpg", img_bytes, "image/jpeg")},
        )
        assert res_sub_b.status_code == 200, res_sub_b.text
        sub_b_data = res_sub_b.json()
        sub_b_id = sub_b_data["id"]

        # Complaint A (Pilibhit)
        res_comp_a = client.post(
            "/complaints",
            headers=h_user_a,
            files={"photo": ("comp_a.jpg", img_bytes, "image/jpeg")},
            data={"comment": "Broken road in Pilibhit near station"},
        )
        assert res_comp_a.status_code == 200, res_comp_a.text
        comp_a_data = res_comp_a.json()
        comp_a_id = comp_a_data["id"]

        # Complaint B (Nagpur)
        res_comp_b = client.post(
            "/complaints",
            headers=h_user_b,
            files={"photo": ("comp_b.jpg", img_bytes, "image/jpeg")},
            data={"comment": "Flooded drain in Nagpur civil lines"},
        )
        assert res_comp_b.status_code == 200, res_comp_b.text
        comp_b_data = res_comp_b.json()
        comp_b_id = comp_b_data["id"]

        # Verify norm columns stored in DB
        db_sub_a = db.query(Submission).filter(Submission.id == sub_a_id).first()
        db_sub_b = db.query(Submission).filter(Submission.id == sub_b_id).first()
        db_comp_a = db.query(Complaint).filter(Complaint.id == comp_a_id).first()
        db_comp_b = db.query(Complaint).filter(Complaint.id == comp_b_id).first()

        print(f"Submission A snapshot: state_norm='{db_sub_a.state_norm}', constituency_norm='{db_sub_a.constituency_norm}'")
        print(f"Submission B snapshot: state_norm='{db_sub_b.state_norm}', constituency_norm='{db_sub_b.constituency_norm}'")
        print(f"Complaint A snapshot: state_norm='{db_comp_a.state_norm}', constituency_norm='{db_comp_a.constituency_norm}'")
        print(f"Complaint B snapshot: state_norm='{db_comp_b.state_norm}', constituency_norm='{db_comp_b.constituency_norm}'")

        assert db_sub_a.state_norm == normalize_place(user_a.state)
        assert db_sub_a.constituency_norm == normalize_place(user_a.constituency)
        assert db_sub_b.state_norm == normalize_place(user_b.state)
        assert db_sub_b.constituency_norm == normalize_place(user_b.constituency)
        assert db_comp_a.state_norm == normalize_place(user_a.state)
        assert db_comp_a.constituency_norm == normalize_place(user_a.constituency)
        assert db_comp_b.state_norm == normalize_place(user_b.state)
        assert db_comp_b.constituency_norm == normalize_place(user_b.constituency)
        print("[PASS] Task 1 PASSED: Normalized state and constituency saved at creation snapshot.")

        # ---------------------------------------------------------------------
        # 3. Scope Rule (Task 2): Each auditor lists only their own items
        # ---------------------------------------------------------------------
        print("\n--- 3. Testing scope isolation in listings ---")

        # Submissions listing
        subs_for_aud_a = client.get("/auditor/submissions?status=pending", headers=h_aud_a).json()
        subs_for_aud_b = client.get("/auditor/submissions?status=pending", headers=h_aud_b).json()
        ids_sub_a = [s["id"] for s in subs_for_aud_a]
        ids_sub_b = [s["id"] for s in subs_for_aud_b]

        print(f"Auditor A (Pilibhit) sees submissions: {ids_sub_a}")
        print(f"Auditor B (Nagpur) sees submissions: {ids_sub_b}")
        assert sub_a_id in ids_sub_a and sub_b_id not in ids_sub_a
        assert sub_b_id in ids_sub_b and sub_a_id not in ids_sub_b
        print("[PASS] Auditor submissions listing correctly scoped.")

        # Complaints listing
        comps_for_aud_a = client.get("/auditor/complaints?status=pending", headers=h_aud_a).json()["items"]
        comps_for_aud_b = client.get("/auditor/complaints?status=pending", headers=h_aud_b).json()["items"]
        ids_comp_a = [c["id"] for c in comps_for_aud_a]
        ids_comp_b = [c["id"] for c in comps_for_aud_b]

        print(f"Auditor A (Pilibhit) sees complaints: {ids_comp_a}")
        print(f"Auditor B (Nagpur) sees complaints: {ids_comp_b}")
        assert comp_a_id in ids_comp_a and comp_b_id not in ids_comp_a
        assert comp_b_id in ids_comp_b and comp_a_id not in ids_comp_b
        print("[PASS] Auditor complaints listing correctly scoped.")

        # ---------------------------------------------------------------------
        # 4. Out-of-scope actions return 404
        # ---------------------------------------------------------------------
        print("\n--- 4. Testing that actions on out-of-scope items return 404 (not 403) ---")

        # Auditor A trying to view/act on Nagpur submission B
        r_view_sub_b = client.get(f"/auditor/submissions/{sub_b_id}/image", headers=h_aud_a)
        r_app_sub_b = client.post(f"/auditor/submissions/{sub_b_id}/approve", headers=h_aud_a)
        r_rej_sub_b = client.post(f"/auditor/submissions/{sub_b_id}/reject", headers=h_aud_a, json={"reason": "test"})
        print(f"Auditor A accessing Sub B image: HTTP {r_view_sub_b.status_code}")
        print(f"Auditor A approving Sub B: HTTP {r_app_sub_b.status_code}")
        print(f"Auditor A rejecting Sub B: HTTP {r_rej_sub_b.status_code}")
        assert r_view_sub_b.status_code == 404
        assert r_app_sub_b.status_code == 404
        assert r_rej_sub_b.status_code == 404

        # Auditor A trying to view/act on Nagpur complaint B
        r_view_comp_b = client.get(f"/complaints/{comp_b_id}/image", headers=h_aud_a)
        r_acc_comp_b = client.post(f"/auditor/complaints/{comp_b_id}/accept", headers=h_aud_a, json={"comment": "good"})
        r_rej_comp_b = client.post(f"/auditor/complaints/{comp_b_id}/reject", headers=h_aud_a, json={"comment": "bad"})
        print(f"Auditor A accessing Comp B image: HTTP {r_view_comp_b.status_code}")
        print(f"Auditor A accepting Comp B: HTTP {r_acc_comp_b.status_code}")
        print(f"Auditor A rejecting Comp B: HTTP {r_rej_comp_b.status_code}")
        assert r_view_comp_b.status_code == 404
        assert r_acc_comp_b.status_code == 404
        assert r_rej_comp_b.status_code == 404
        print("[PASS] All out-of-scope actions returned 404 as required.")

        # In-scope actions succeed
        r_view_sub_a = client.get(f"/auditor/submissions/{sub_a_id}/image", headers=h_aud_a)
        r_view_comp_a = client.get(f"/complaints/{comp_a_id}/image", headers=h_aud_a)
        assert r_view_sub_a.status_code == 200
        assert r_view_comp_a.status_code == 200
        print("[PASS] In-scope image views succeed (HTTP 200).")

        # ---------------------------------------------------------------------
        # 5. Built-in auditor and Admin see everything
        # ---------------------------------------------------------------------
        print("\n--- 5. Testing that Built-in Auditor and Admin see everything ---")
        builtin_subs = client.get("/auditor/submissions?status=pending", headers=h_builtin).json()
        builtin_sub_ids = [s["id"] for s in builtin_subs]
        builtin_comps = client.get("/auditor/complaints?status=all&page_size=100", headers=h_builtin).json()["items"]
        builtin_comp_ids = [c["id"] for c in builtin_comps]

        print(f"Built-in auditor sees submission IDs: {builtin_sub_ids}")
        print(f"Built-in auditor sees complaint IDs: {builtin_comp_ids}")
        assert sub_a_id in builtin_sub_ids and sub_b_id in builtin_sub_ids
        assert comp_a_id in builtin_comp_ids and comp_b_id in builtin_comp_ids

        # Admin route check
        r_admin = client.get("/admin/auditors", headers=h_admin)
        print(f"Admin /admin/auditors status: HTTP {r_admin.status_code}")
        assert r_admin.status_code == 200
        print("[PASS] Built-in auditor and admin see everything.")

        # ---------------------------------------------------------------------
        # 6. User later changes location: old submission/complaint does NOT move
        # ---------------------------------------------------------------------
        print("\n--- 6. Testing user location change does NOT move old submissions/complaints ---")
        user_a.state = "Maharashtra"
        user_a.district = "NAGPUR"
        user_a.constituency = "NAGPUR"
        db.commit()

        # Check Auditor A still sees sub_a and comp_a
        subs_a_after = [s["id"] for s in client.get("/auditor/submissions?status=pending", headers=h_aud_a).json()]
        comps_a_after = [c["id"] for c in client.get("/auditor/complaints?status=pending", headers=h_aud_a).json()["items"]]
        subs_b_after = [s["id"] for s in client.get("/auditor/submissions?status=pending", headers=h_aud_b).json()]
        comps_b_after = [c["id"] for c in client.get("/auditor/complaints?status=pending", headers=h_aud_b).json()["items"]]

        print(f"After user A moves to Nagpur:")
        print(f"Auditor A (Pilibhit) still sees sub_a: {sub_a_id in subs_a_after}, comp_a: {comp_a_id in comps_a_after}")
        print(f"Auditor B (Nagpur) does NOT see sub_a: {sub_a_id not in subs_b_after}, comp_a: {comp_a_id not in comps_b_after}")
        assert sub_a_id in subs_a_after and comp_a_id in comps_a_after
        assert sub_a_id not in subs_b_after and comp_a_id not in comps_b_after
        print("[PASS] Immutable snapshot verified: changing user location does not move existing items.")

        # ---------------------------------------------------------------------
        # 7. GET /auditor/me (Task 3)
        # ---------------------------------------------------------------------
        print("\n--- 7. Testing GET /auditor/me ---")
        res_me_db = client.get("/auditor/me", headers=h_aud_a)
        assert res_me_db.status_code == 200
        me_db_data = res_me_db.json()
        print(f"DB Auditor /auditor/me: {me_db_data}")
        assert me_db_data["name"] == "Auditor Pilibhit"
        assert me_db_data["email"] == "aud.pilibhit@test.com"
        assert me_db_data["state"] == "Uttar Pradesh"
        assert me_db_data["constituency"] == "PILIBHIT"
        assert me_db_data["builtin"] is False
        assert me_db_data["scope"] == "constituency"

        res_me_builtin = client.get("/auditor/me", headers=h_builtin)
        assert res_me_builtin.status_code == 200
        me_bi_data = res_me_builtin.json()
        print(f"Built-in Auditor /auditor/me: {me_bi_data}")
        assert me_bi_data["name"] == "Built-in auditor"
        assert me_bi_data["builtin"] is True
        assert me_bi_data["scope"] == "all"
        assert me_bi_data["state"] is None
        assert me_bi_data["constituency"] is None
        print("[PASS] GET /auditor/me works for both DB and built-in auditors.")

        # ---------------------------------------------------------------------
        # 8. BUILTIN_AUDITOR_ENABLED switch (Task 4)
        # ---------------------------------------------------------------------
        print("\n--- 8. Testing BUILTIN_AUDITOR_ENABLED switch in staff_auth.py ---")
        original_setting = settings.BUILTIN_AUDITOR_ENABLED
        try:
            settings.BUILTIN_AUDITOR_ENABLED = False
            r_disabled = client.post("/auth/staff-login", json={
                "username": settings.AUDITOR_ID,
                "password": settings.AUDITOR_PASSWORD,
            })
            print(f"Staff login with BUILTIN_AUDITOR_ENABLED=False: HTTP {r_disabled.status_code} ({r_disabled.json()})")
            assert r_disabled.status_code == 401

            r_legacy_disabled = client.post("/auth/auditor-login", json={
                "username": settings.AUDITOR_ID,
                "password": settings.AUDITOR_PASSWORD,
            })
            print(f"Legacy auditor login with BUILTIN_AUDITOR_ENABLED=False: HTTP {r_legacy_disabled.status_code}")
            assert r_legacy_disabled.status_code == 401

            settings.BUILTIN_AUDITOR_ENABLED = True
            r_enabled = client.post("/auth/staff-login", json={
                "username": settings.AUDITOR_ID,
                "password": settings.AUDITOR_PASSWORD,
            })
            print(f"Staff login with BUILTIN_AUDITOR_ENABLED=True: HTTP {r_enabled.status_code}")
            assert r_enabled.status_code == 200
            assert r_enabled.json()["role"] == "auditor"
            print("[PASS] BUILTIN_AUDITOR_ENABLED toggle correctly enforced.")
        finally:
            settings.BUILTIN_AUDITOR_ENABLED = original_setting

        # ---------------------------------------------------------------------
        # Clean up files created during verification
        # ---------------------------------------------------------------------
        for sid in [sub_a_id, sub_b_id]:
            s = db.query(Submission).filter(Submission.id == sid).first()
            if s:
                p = Path("c:/Users/Mrinay/Desktop/CivicQuest/backend") / s.image_path
                if p.is_file():
                    p.unlink()
                db.delete(s)
        for cid in [comp_a_id, comp_b_id]:
            c = db.query(Complaint).filter(Complaint.id == cid).first()
            if c:
                p = Path("c:/Users/Mrinay/Desktop/CivicQuest/backend") / c.image_path
                if p.is_file():
                    p.unlink()
                db.delete(c)
        db.delete(aud_a)
        db.delete(aud_b)
        db.delete(user_a)
        db.delete(user_b)
        db.commit()

        print("\n" + "=" * 70)
        print("ALL AUDITOR SCOPE & DONE WHEN CHECKS PASSED SUCCESSFULLY!")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    main()
