import sys
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import User, Work
from app.security import create_token

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def run_tests():
    client = TestClient(app)
    db = SessionLocal()
    try:
        # Test 1: User without location
        user_no_loc = db.query(User).filter(User.email == "no.loc@gmail.com").first()
        if not user_no_loc:
            user_no_loc = User(
                email="no.loc@gmail.com",
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

        token_no_loc = create_token(sub=str(user_no_loc.id), role="user")
        res_no_loc = client.get(
            "/works", headers={"Authorization": f"Bearer {token_no_loc}"}
        )
        print("=== Test 1: User with no location gets 400 ===")
        print("Status:", res_no_loc.status_code, "| Detail:", res_no_loc.json())
        assert res_no_loc.status_code == 400
        assert res_no_loc.json()["detail"] == "Location not set"

        # Test 2: User with real location: Uttar Pradesh, PILIBHIT, PILIBHIT
        user_loc = (
            db.query(User).filter(User.email == "pilibhit.citizen@gmail.com").first()
        )
        if not user_loc:
            user_loc = User(
                email="pilibhit.citizen@gmail.com",
                otp_secret="JBSWY3DPEHPK3PXP",
                state="Uttar Pradesh",
                district="PILIBHIT",
                constituency="PILIBHIT",
            )
            db.add(user_loc)
            db.commit()
            db.refresh(user_loc)
        else:
            user_loc.state = "Uttar Pradesh"
            user_loc.district = "PILIBHIT"
            user_loc.constituency = "PILIBHIT"
            db.commit()

        token_loc = create_token(sub=str(user_loc.id), role="user")
        res_works = client.get(
            "/works?page=1&page_size=20",
            headers={"Authorization": f"Bearer {token_loc}"},
        )
        print("\n=== Test 2: User with location gets matching works ===")
        print("Status:", res_works.status_code)
        data = res_works.json()
        print("Total matching works in Pilibhit:", data["total"])
        items = data["items"]
        print("Items returned on page 1:", len(items))

        # Check matching rule strictly
        for item in items:
            if item["source"] == "LS":
                assert item["state"].upper() == "UTTAR PRADESH"
                assert item["district"].upper() == "PILIBHIT"
                assert item["constituency"].upper() == "PILIBHIT"
            elif item["source"] == "RS":
                assert item["state"].upper() == "UTTAR PRADESH"
                assert item["district"].upper() == "PILIBHIT"
                assert item["constituency"] is None

        # Fetch LS and RS examples
        all_res = client.get(
            "/works?page=1&page_size=100",
            headers={"Authorization": f"Bearer {token_loc}"},
        ).json()["items"]
        ls_examples = [x for x in all_res if x["source"] == "LS"]
        rs_examples = [x for x in all_res if x["source"] == "RS"]

        print("\n--- ONE LOK SABHA (LS) EXAMPLE ---")
        ls_ex = ls_examples[0]
        print(f"ID: {ls_ex['id']} | Source: {ls_ex['source']} | Code: {ls_ex['work_code']}")
        print(f"Type: {ls_ex['work_type']}")
        print(f"Description: {ls_ex['description']}")
        print(f"State: {ls_ex['state']} | District: {ls_ex['district']} | Constituency: {ls_ex['constituency']}")
        print(f"MP: {ls_ex['mp_name']} | Amount: ₹{ls_ex['amount']} | Date: {ls_ex['completion_date']}")
        print(f"My Submission Status: {ls_ex['my_submission_status']}")

        print("\n--- ONE RAJYA SABHA (RS) EXAMPLE ---")
        rs_ex = rs_examples[0]
        print(f"ID: {rs_ex['id']} | Source: {rs_ex['source']} | Code: {rs_ex['work_code']}")
        print(f"Type: {rs_ex['work_type']}")
        print(f"Description: {rs_ex['description']}")
        print(f"State: {rs_ex['state']} | District: {rs_ex['district']} | Constituency: {rs_ex['constituency']}")
        print(f"MP: {rs_ex['mp_name']} | Amount: ₹{rs_ex['amount']} | Date: {rs_ex['completion_date']}")
        print(f"My Submission Status: {rs_ex['my_submission_status']}")

        print("\n=== Test 3: Search filter ===")
        res_search = client.get(
            "/works?search=lights", headers={"Authorization": f"Bearer {token_loc}"}
        )
        search_data = res_search.json()
        print("Search 'lights' matched:", search_data["total"], "items")
        assert search_data["total"] > 0
        for it in search_data["items"][:3]:
            text_check = (it["description"] + " " + it["work_type"]).lower()
            assert "lights" in text_check
            print(f"  - [{it['source']}] {it['work_type'][:40]}...")

        print("\n=== Test 4: Sorting by completion_date descending ===")
        dates = [it["completion_date"] for it in data["items"] if it["completion_date"]]
        assert dates == sorted(dates, reverse=True), "Not sorted by date descending"
        print("Dates descending order: Verified")

        print("\nALL STEP B6 CHECKS PASSED!")
    finally:
        db.close()


if __name__ == "__main__":
    run_tests()
