import hashlib
import re
from datetime import date
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import Auditor
from app.security import create_token, init_admin_credentials, init_auditor_credentials


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


@pytest.fixture(autouse=True)
def setup_credentials():
    init_auditor_credentials()
    init_admin_credentials()


def _admin_headers():
    token = create_token(sub=settings.ADMIN_ID, role="admin")
    return {"Authorization": f"Bearer {token}"}


def _auditor_headers():
    token = create_token(sub=settings.AUDITOR_ID, role="auditor")
    return {"Authorization": f"Bearer {token}"}


def _user_headers(user_id: int = 1):
    token = create_token(sub=str(user_id), role="user")
    return {"Authorization": f"Bearer {token}"}


def _cleanup_auditor(db, email: str):
    auditors = db.query(Auditor).filter(Auditor.email == email.lower()).all()
    for a in auditors:
        db.delete(a)
    db.commit()


# ---------------------------------------------------------------------------
# TASK 1: Admin-only routes (admin_auditors.py)
# ---------------------------------------------------------------------------

def test_user_and_auditor_tokens_forbidden_on_admin_routes(client):
    user_h = _user_headers()
    auditor_h = _auditor_headers()

    admin_endpoints = [
        ("POST", "/admin/auditors", {
            "name": "Forbidden Test",
            "dob": "1995-05-15",
            "email": "forbidtest@gmail.com",
            "state": "Uttar Pradesh",
            "district": "PILIBHIT",
            "status": "active",
        }),
        ("PATCH", "/admin/auditors/1/status", {"status": "disabled"}),
        ("POST", "/admin/auditors/1/resend-invite", {}),
        ("GET", "/admin/location/options", None),
    ]

    for method, path, json_data in admin_endpoints:
        # Check user token -> 403
        if method == "POST":
            r_user = client.post(path, headers=user_h, json=json_data)
            r_aud = client.post(path, headers=auditor_h, json=json_data)
        elif method == "PATCH":
            r_user = client.patch(path, headers=user_h, json=json_data)
            r_aud = client.patch(path, headers=auditor_h, json=json_data)
        else:
            r_user = client.get(path, headers=user_h)
            r_aud = client.get(path, headers=auditor_h)

        assert r_user.status_code == 403, f"User expected 403 on {method} {path}, got {r_user.status_code}"
        assert r_aud.status_code == 403, f"Auditor expected 403 on {method} {path}, got {r_aud.status_code}"


def test_admin_location_options(client):
    admin_h = _admin_headers()
    res = client.get("/admin/location/options", headers=admin_h)
    assert res.status_code == 200
    data = res.json()
    assert "states" in data
    assert "districts" in data
    assert "constituencies" in data
    assert len(data["states"]) > 0


def test_create_auditor_age_validation(client):
    admin_h = _admin_headers()
    # 17-year-old DOB -> 400/422
    today = date.today()
    dob_17 = date(today.year - 17, today.month, today.day).isoformat()
    r = client.post("/admin/auditors", headers=admin_h, json={
        "name": "Underage Auditor",
        "dob": dob_17,
        "email": "underage@gmail.com",
        "state": "Uttar Pradesh",
        "district": "PILIBHIT",
        "status": "active",
    })
    assert r.status_code in (400, 422), f"Expected 400/422 for 17-year-old DOB, got {r.status_code}"

    # Future DOB -> 400/422
    dob_future = date(today.year + 1, today.month, today.day).isoformat()
    r_fut = client.post("/admin/auditors", headers=admin_h, json={
        "name": "Future Auditor",
        "dob": dob_future,
        "email": "future@gmail.com",
        "state": "Uttar Pradesh",
        "district": "PILIBHIT",
        "status": "active",
    })
    assert r_fut.status_code in (400, 422)


def test_create_auditor_duplicate_email(client, db, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_USER", "")
    email = "dup.auditor.test@gmail.com"
    _cleanup_auditor(db, email)

    admin_h = _admin_headers()
    payload = {
        "name": "Duplicate Tester",
        "dob": "1990-01-01",
        "email": email,
        "state": "Uttar Pradesh",
        "district": "PILIBHIT",
        "status": "active",
    }
    r1 = client.post("/admin/auditors", headers=admin_h, json=payload)
    assert r1.status_code == 201

    r2 = client.post("/admin/auditors", headers=admin_h, json=payload)
    assert r2.status_code == 409
    assert "already exists" in r2.json()["detail"].lower()

    _cleanup_auditor(db, email)


# ---------------------------------------------------------------------------
# Complete Flow & Acceptance Criteria Test
# ---------------------------------------------------------------------------

def test_full_auditor_lifecycle(client, db, capsys, monkeypatch):
    # Test dev mode where link is printed to console
    monkeypatch.setattr(settings, "SMTP_USER", "")

    email = "flow.auditor@gmail.com"
    _cleanup_auditor(db, email)

    admin_h = _admin_headers()

    # 1. Create auditor prints or sends link, returns 201
    create_res = client.post("/admin/auditors", headers=admin_h, json={
        "name": "Ramesh Kumar",
        "dob": "1992-03-10",
        "email": email,
        "state": "Uttar Pradesh",
        "district": "PILIBHIT",
        "constituency": "PILIBHIT",
        "status": "active",
    })
    assert create_res.status_code == 201
    data = create_res.json()
    auditor_id = data["id"]
    assert data["name"] == "Ramesh Kumar"
    assert data["email"] == email
    assert data["status"] == "active"
    assert data["email_sent"] is True
    # Ensure no secrets in response
    assert "password_hash" not in data
    assert "invite_token_hash" not in data
    assert "token" not in data

    # Verify console output contains the invite link
    captured = capsys.readouterr()
    assert "[DEV MODE] Auditor invite link for flow.auditor@gmail.com:" in captured.out

    # Retrieve the invite token from printed link
    match = re.search(r"token=([a-zA-Z0-9_-]+)", captured.out)
    assert match is not None, "Token must be printed in console dev mode"
    token = match.group(1)

    # Verify database state
    auditor_row = db.query(Auditor).filter(Auditor.id == auditor_id).first()
    assert auditor_row is not None
    assert auditor_row.password_hash is None
    expected_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert auditor_row.invite_token_hash == expected_hash
    assert auditor_row.invite_expires_at is not None

    # 2. Public route: GET /auth/auditor-invite/{token} shows name and email
    invite_res = client.get(f"/auth/auditor-invite/{token}")
    assert invite_res.status_code == 200
    invite_data = invite_res.json()
    assert invite_data["name"] == "Ramesh Kumar"
    assert invite_data["email"] == email

    # Invalid token gives 404
    inv_res = client.get("/auth/auditor-invite/invalidtoken123")
    assert inv_res.status_code == 404

    # 3. Setting a password works once
    new_password = "SecretPassword123"
    set_pwd_res = client.post("/auth/auditor-set-password", json={
        "token": token,
        "password": new_password,
    })
    assert set_pwd_res.status_code == 200
    assert set_pwd_res.json()["message"] == "Password set successfully"

    # Second use of the same token returns 404
    second_use_res = client.post("/auth/auditor-set-password", json={
        "token": token,
        "password": "AnotherPassword456",
    })
    assert second_use_res.status_code == 404

    # GET /auth/auditor-invite/{token} now also returns 404
    invite_used_res = client.get(f"/auth/auditor-invite/{token}")
    assert invite_used_res.status_code == 404

    # 4. After setting password, staff-login works with the Gmail and password
    login_res = client.post("/auth/staff-login", json={
        "username": email,
        "password": new_password,
    })
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert login_data["role"] == "auditor"
    auditor_jwt = login_data["access_token"]
    db_auditor_headers = {"Authorization": f"Bearer {auditor_jwt}"}

    # Already-issued token works on /auditor/submissions
    subs_res = client.get("/auditor/submissions", headers=db_auditor_headers)
    assert subs_res.status_code == 200

    # 5. Resend-invite fails with 409 because password is already set
    resend_res = client.post(f"/admin/auditors/{auditor_id}/resend-invite", headers=admin_h)
    assert resend_res.status_code == 409

    # 6. PATCH status "disabled"
    patch_res = client.patch(
        f"/admin/auditors/{auditor_id}/status",
        headers=admin_h,
        json={"status": "disabled"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "disabled"

    # Next staff-login returns 403
    login_disabled_res = client.post("/auth/staff-login", json={
        "username": email,
        "password": new_password,
    })
    assert login_disabled_res.status_code == 403

    # Already-issued auditor token gets 403 on /auditor/submissions
    subs_disabled_res = client.get("/auditor/submissions", headers=db_auditor_headers)
    assert subs_disabled_res.status_code == 403

    # 7. Re-enable status to "active"
    patch_active = client.patch(
        f"/admin/auditors/{auditor_id}/status",
        headers=admin_h,
        json={"status": "active"},
    )
    assert patch_active.status_code == 200
    assert patch_active.json()["status"] == "active"

    # Staff-login works again
    login_active_res = client.post("/auth/staff-login", json={
        "username": email,
        "password": new_password,
    })
    assert login_active_res.status_code == 200

    # 8. Test resend-invite on an auditor who hasn't set password yet
    email2 = "auditor.no.pass@gmail.com"
    _cleanup_auditor(db, email2)
    c2 = client.post("/admin/auditors", headers=admin_h, json={
        "name": "No Password Auditor",
        "dob": "1994-04-12",
        "email": email2,
        "state": "Uttar Pradesh",
        "district": "PILIBHIT",
        "status": "active",
    })
    aud2_id = c2.json()["id"]

    resend_ok = client.post(f"/admin/auditors/{aud2_id}/resend-invite", headers=admin_h)
    assert resend_ok.status_code == 200
    assert resend_ok.json()["email_sent"] is True

    # 9. 404 on unknown auditor id
    assert client.patch("/admin/auditors/999999/status", headers=admin_h, json={"status": "disabled"}).status_code == 404
    assert client.post("/admin/auditors/999999/resend-invite", headers=admin_h).status_code == 404

    # Clean up
    _cleanup_auditor(db, email)
    _cleanup_auditor(db, email2)
