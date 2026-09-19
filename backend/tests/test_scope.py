"""
Tests for the constituency-scoped auditor system (Tasks 1-4).

Done-when coverage:
  - Two DB auditors in different constituencies each see only their own items.
  - Opening or approving an out-of-scope item returns 404 (not 403).
  - Built-in auditor sees everything.
  - Admin sees everything (via admin_views.py).
  - A user who later changes location does NOT move an old complaint to another auditor.
  - New uploads store the norm columns correctly.
  - GET /auditor/me works for both built-in and DB auditors.
  - BUILTIN_AUDITOR_ENABLED=false blocks built-in login with 401.
"""

import io
from datetime import date
from pathlib import Path

import bcrypt
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import Auditor, Complaint, Submission, User, XPLog
from app.security import create_token, init_auditor_credentials, init_admin_credentials
from app.services.normalize import normalize_place


@pytest.fixture(autouse=True)
def ensure_credentials():
    init_auditor_credentials()
    init_admin_credentials()


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


def _make_image_bytes() -> bytes:
    img = Image.new("RGB", (80, 80), color=(30, 60, 90))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def _make_auditor(db, *, name, email, state, constituency):
    old = db.query(Auditor).filter(Auditor.email == email.lower()).first()
    if old:
        db.delete(old)
        db.commit()
    a = Auditor(
        name=name, dob=date(1990, 1, 1), email=email.lower(),
        state=state, district="Test District", constituency=constituency,
        status="active", password_hash=_hash_pw("testpass"),
    )
    db.add(a); db.commit(); db.refresh(a)
    return a


def _make_user(db, *, email, state, constituency):
    old = db.query(User).filter(User.email == email).first()
    if old:
        db.query(XPLog).filter(XPLog.user_id == old.id).delete()
        db.query(Submission).filter(Submission.user_id == old.id).delete()
        db.query(Complaint).filter(Complaint.user_id == old.id).delete()
        db.delete(old); db.commit()
    u = User(email=email, otp_secret="JBSWY3DPEHPK3PXP",
             state=state, district="Test District", constituency=constituency, xp=0)
    db.add(u); db.commit(); db.refresh(u)
    return u


def _upload_complaint(client, user_token, comment="This road has a huge pothole near the main junction"):
    r = client.post(
        "/complaints",
        headers={"Authorization": f"Bearer {user_token}"},
        files={"photo": ("c.jpg", _make_image_bytes(), "image/jpeg")},
        data={"comment": comment},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _auditor_token(aud):
    return create_token(sub=aud.email, role="auditor", extra={"auditor_id": aud.id})


def _builtin_token():
    return create_token(sub=settings.AUDITOR_ID, role="auditor")


def _admin_token():
    return create_token(sub=settings.ADMIN_ID, role="admin")


def _cleanup_complaint(db, c_data):
    c_id = c_data["id"] if isinstance(c_data, dict) else c_data.id
    complaint = db.query(Complaint).filter(Complaint.id == c_id).first()
    if complaint:
        p = Path("c:/Users/Mrinay/Desktop/CivicQuest/backend") / complaint.image_path
        if p.is_file():
            p.unlink()
        db.delete(complaint)
        db.commit()


# ---- Task 1: snapshot columns -----------------------------------------------

def test_complaint_stores_norm_columns(db):
    u = _make_user(db, email="snap.user@gmail.com", state="Uttar Pradesh", constituency="PILIBHIT")
    token = create_token(sub=str(u.id), role="user")
    with TestClient(app) as c:
        c_data = _upload_complaint(c, token)
    complaint = db.query(Complaint).filter(Complaint.id == c_data["id"]).first()
    assert complaint.state_norm == normalize_place("Uttar Pradesh")
    assert complaint.constituency_norm == normalize_place("PILIBHIT")
    _cleanup_complaint(db, c_data)


# ---- Task 2: scope isolation ------------------------------------------------

def test_each_auditor_sees_only_own_complaints(client, db):
    aud_a = _make_auditor(db, name="Aud A", email="aud.a.scope@test.com",
                          state="Uttar Pradesh", constituency="PILIBHIT")
    aud_b = _make_auditor(db, name="Aud B", email="aud.b.scope@test.com",
                          state="Rajasthan", constituency="JAIPUR")
    user_a = _make_user(db, email="user.a.scope@gmail.com", state="Uttar Pradesh", constituency="PILIBHIT")
    user_b = _make_user(db, email="user.b.scope@gmail.com", state="Rajasthan", constituency="JAIPUR")
    tok_a = create_token(sub=str(user_a.id), role="user")
    tok_b = create_token(sub=str(user_b.id), role="user")
    c_a = _upload_complaint(client, tok_a)
    c_b = _upload_complaint(client, tok_b)

    ha = {"Authorization": f"Bearer {_auditor_token(aud_a)}"}
    hb = {"Authorization": f"Bearer {_auditor_token(aud_b)}"}
    hbi = {"Authorization": f"Bearer {_builtin_token()}"}

    ids_a = {it["id"] for it in client.get("/auditor/complaints?status=pending", headers=ha).json()["items"]}
    assert c_a["id"] in ids_a and c_b["id"] not in ids_a

    ids_b = {it["id"] for it in client.get("/auditor/complaints?status=pending", headers=hb).json()["items"]}
    assert c_b["id"] in ids_b and c_a["id"] not in ids_b

    ids_bi = {it["id"] for it in client.get("/auditor/complaints?status=all", headers=hbi).json()["items"]}
    assert c_a["id"] in ids_bi and c_b["id"] in ids_bi

    _cleanup_complaint(db, c_a); _cleanup_complaint(db, c_b)


def test_out_of_scope_complaint_returns_404(client, db):
    aud_a = _make_auditor(db, name="Aud A 404", email="aud.a.404@test.com",
                          state="Uttar Pradesh", constituency="PILIBHIT")
    user_b = _make_user(db, email="user.b.404@gmail.com", state="Rajasthan", constituency="JAIPUR")
    tok_b = create_token(sub=str(user_b.id), role="user")
    c_b = _upload_complaint(client, tok_b)

    ha = {"Authorization": f"Bearer {_auditor_token(aud_a)}"}

    assert client.post(f"/auditor/complaints/{c_b['id']}/accept", headers=ha, json={"comment": "nope"}).status_code == 404
    assert client.post(f"/auditor/complaints/{c_b['id']}/reject", headers=ha, json={"comment": "nope"}).status_code == 404
    assert client.get(f"/complaints/{c_b['id']}/image", headers=ha).status_code == 404

    _cleanup_complaint(db, c_b)


def test_builtin_sees_all_complaints(client, db):
    user_b = _make_user(db, email="user.bi.all@gmail.com", state="Rajasthan", constituency="JAIPUR")
    tok_b = create_token(sub=str(user_b.id), role="user")
    c_b = _upload_complaint(client, tok_b)

    hbi = {"Authorization": f"Bearer {_builtin_token()}"}
    ids = {it["id"] for it in client.get("/auditor/complaints?status=all&page_size=100", headers=hbi).json()["items"]}
    assert c_b["id"] in ids

    _cleanup_complaint(db, c_b)


def test_admin_sees_admin_routes(client):
    ha = {"Authorization": f"Bearer {_admin_token()}"}
    r = client.get("/admin/location/options", headers=ha)
    assert r.status_code == 200


# ---- Task 2: snapshot immutability ------------------------------------------

def test_changing_user_location_does_not_move_complaint(client, db):
    aud_a = _make_auditor(db, name="Immut A", email="immut.a@test.com",
                          state="Uttar Pradesh", constituency="PILIBHIT")
    aud_b = _make_auditor(db, name="Immut B", email="immut.b@test.com",
                          state="Rajasthan", constituency="JAIPUR")
    user = _make_user(db, email="immut.user@gmail.com", state="Uttar Pradesh", constituency="PILIBHIT")
    tok = create_token(sub=str(user.id), role="user")
    c_data = _upload_complaint(client, tok)
    c_id = c_data["id"]

    complaint = db.query(Complaint).filter(Complaint.id == c_id).first()
    assert complaint.state_norm == normalize_place("Uttar Pradesh")
    assert complaint.constituency_norm == normalize_place("PILIBHIT")

    # Move user to constituency B
    user.state = "Rajasthan"; user.district = "Dist B"; user.constituency = "JAIPUR"
    db.commit()

    ha = {"Authorization": f"Bearer {_auditor_token(aud_a)}"}
    hb = {"Authorization": f"Bearer {_auditor_token(aud_b)}"}

    ids_a = {it["id"] for it in client.get("/auditor/complaints?status=all&page_size=100", headers=ha).json()["items"]}
    assert c_id in ids_a, "Auditor A must still see the frozen complaint"

    ids_b = {it["id"] for it in client.get("/auditor/complaints?status=all&page_size=100", headers=hb).json()["items"]}
    assert c_id not in ids_b, "Auditor B must NOT see the old complaint"

    _cleanup_complaint(db, c_data)


# ---- Task 3: GET /auditor/me ------------------------------------------------

def test_db_auditor_me(client, db):
    aud = _make_auditor(db, name="Me Test", email="me.test@test.com",
                        state="Uttar Pradesh", constituency="PILIBHIT")
    h = {"Authorization": f"Bearer {_auditor_token(aud)}"}
    r = client.get("/auditor/me", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Me Test"
    assert data["email"] == "me.test@test.com"
    assert data["state"] == "Uttar Pradesh"
    assert data["constituency"] == "PILIBHIT"
    assert data["builtin"] is False
    assert data["scope"] == "constituency"


def test_builtin_auditor_me(client):
    h = {"Authorization": f"Bearer {_builtin_token()}"}
    r = client.get("/auditor/me", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["builtin"] is True
    assert data["scope"] == "all"
    assert data["state"] is None
    assert data["constituency"] is None


def test_user_cannot_access_auditor_me(client, db):
    u = _make_user(db, email="useme@gmail.com", state="UP", constituency="TEST")
    tok = create_token(sub=str(u.id), role="user")
    r = client.get("/auditor/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


# ---- Task 4: BUILTIN_AUDITOR_ENABLED switch ---------------------------------

def test_builtin_login_blocked_when_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "BUILTIN_AUDITOR_ENABLED", False)
    r = client.post("/auth/staff-login", json={
        "username": settings.AUDITOR_ID,
        "password": settings.AUDITOR_PASSWORD,
    })
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid ID or password"


def test_builtin_login_works_when_enabled(client):
    r = client.post("/auth/staff-login", json={
        "username": settings.AUDITOR_ID,
        "password": settings.AUDITOR_PASSWORD,
    })
    assert r.status_code == 200
    assert r.json()["role"] == "auditor"


def test_legacy_auditor_login_blocked_when_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "BUILTIN_AUDITOR_ENABLED", False)
    r = client.post("/auth/auditor-login", json={
        "username": settings.AUDITOR_ID,
        "password": settings.AUDITOR_PASSWORD,
    })
    assert r.status_code == 401
