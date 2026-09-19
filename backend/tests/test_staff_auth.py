"""
Tests for POST /auth/staff-login and related security guarantees.
"""
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import bcrypt

from app.database import Base, get_db
from app.main import app
from app.models import Auditor
from app.security import create_token, init_admin_credentials, init_auditor_credentials
from app.config import settings

# Reset the in-memory rate-limiter between tests
import app.routers.staff_auth as _sa

# ---------------------------------------------------------------------------
# In-memory SQLite test database
# ---------------------------------------------------------------------------
TEST_DB_URL = "sqlite:///./test_staff_auth.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def reset_db_and_rate_limiter():
    Base.metadata.create_all(bind=engine)
    # Reset in-memory rate-limiter between tests
    with _sa._rate_lock:
        _sa._fail_tracker.clear()
    # Ensure in-memory hashes are initialised
    init_auditor_credentials()
    init_admin_credentials()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def make_auditor(db, email: str, password: str, status: str = "active") -> Auditor:
    a = Auditor(
        name="Test Auditor",
        dob=date(1990, 1, 1),
        email=email.lower(),
        state="Test State",
        district="Test District",
        status=status,
        password_hash=_hash_pw(password),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


# ---------------------------------------------------------------------------
# TASK 3: staff-login tests
# ---------------------------------------------------------------------------

class TestStaffLoginAdmin:
    def test_admin_correct_credentials(self, client):
        r = client.post("/auth/staff-login", json={
            "username": settings.ADMIN_ID,
            "password": settings.ADMIN_PASSWORD,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["role"] == "admin"
        assert "access_token" in data

    def test_admin_case_insensitive_username(self, client):
        r = client.post("/auth/staff-login", json={
            "username": settings.ADMIN_ID.upper(),
            "password": settings.ADMIN_PASSWORD,
        })
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_admin_wrong_password(self, client):
        r = client.post("/auth/staff-login", json={
            "username": settings.ADMIN_ID,
            "password": "wrongpassword",
        })
        assert r.status_code == 401
        assert r.json()["detail"] == "Invalid ID or password"


class TestStaffLoginBuiltinAuditor:
    def test_builtin_auditor_correct(self, client):
        r = client.post("/auth/staff-login", json={
            "username": settings.AUDITOR_ID,
            "password": settings.AUDITOR_PASSWORD,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["role"] == "auditor"
        assert "access_token" in data

    def test_builtin_auditor_wrong_password(self, client):
        r = client.post("/auth/staff-login", json={
            "username": settings.AUDITOR_ID,
            "password": "wrong",
        })
        assert r.status_code == 401
        assert r.json()["detail"] == "Invalid ID or password"


class TestStaffLoginDBauditor:
    def test_db_auditor_correct(self, client, db):
        make_auditor(db, "auditor@test.com", "securepass123")
        r = client.post("/auth/staff-login", json={
            "username": "auditor@test.com",
            "password": "securepass123",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["role"] == "auditor"

    def test_db_auditor_wrong_password(self, client, db):
        make_auditor(db, "auditor2@test.com", "correctpass")
        r = client.post("/auth/staff-login", json={
            "username": "auditor2@test.com",
            "password": "wrongpass",
        })
        assert r.status_code == 401
        assert r.json()["detail"] == "Invalid ID or password"

    def test_db_auditor_disabled_correct_password(self, client, db):
        """Status check fires AFTER password verification."""
        make_auditor(db, "disabled@test.com", "mypassword", status="disabled")
        r = client.post("/auth/staff-login", json={
            "username": "disabled@test.com",
            "password": "mypassword",
        })
        assert r.status_code == 403
        assert "disabled" in r.json()["detail"]

    def test_unknown_user_returns_401(self, client):
        r = client.post("/auth/staff-login", json={
            "username": "nobody@test.com",
            "password": "whatever",
        })
        assert r.status_code == 401
        assert r.json()["detail"] == "Invalid ID or password"

    def test_last_login_updated_on_success(self, client, db):
        a = make_auditor(db, "logintrack@test.com", "pass123")
        assert a.last_login_at is None
        client.post("/auth/staff-login", json={
            "username": "logintrack@test.com",
            "password": "pass123",
        })
        db.refresh(a)
        assert a.last_login_at is not None


class TestRateLimiter:
    def test_lockout_after_5_failures(self, client):
        username = "ratelimited@test.com"
        for _ in range(5):
            r = client.post("/auth/staff-login", json={
                "username": username, "password": "wrong"
            })
            assert r.status_code == 401

        # 6th attempt must be 429
        r = client.post("/auth/staff-login", json={
            "username": username, "password": "wrong"
        })
        assert r.status_code == 429

    def test_correct_login_clears_fail_count(self, client, db):
        make_auditor(db, "cleartest@test.com", "rightpass")
        # 4 wrong attempts
        for _ in range(4):
            client.post("/auth/staff-login", json={
                "username": "cleartest@test.com", "password": "wrong"
            })
        # correct login clears the counter
        r = client.post("/auth/staff-login", json={
            "username": "cleartest@test.com", "password": "rightpass"
        })
        assert r.status_code == 200
        # After clearing, 5 more failures should lock again
        for _ in range(5):
            client.post("/auth/staff-login", json={
                "username": "cleartest@test.com", "password": "wrong"
            })
        r = client.post("/auth/staff-login", json={
            "username": "cleartest@test.com", "password": "wrong"
        })
        assert r.status_code == 429


# ---------------------------------------------------------------------------
# TASK 4: Token-based access control
# ---------------------------------------------------------------------------

class TestTokenAccessControl:
    def _admin_token(self):
        return create_token(sub=settings.ADMIN_ID, role="admin")

    def _user_token(self, uid: int = 999):
        return create_token(sub=str(uid), role="user")

    def _auditor_token(self):
        return create_token(sub=settings.AUDITOR_ID, role="auditor")

    def test_admin_token_blocked_on_user_works(self, client):
        r = client.get(
            "/works?page=1&page_size=5&source=LS",
            headers={"Authorization": f"Bearer {self._admin_token()}"},
        )
        assert r.status_code == 403

    def test_admin_token_blocked_on_auditor_submissions(self, client):
        r = client.get(
            "/auditor/submissions",
            headers={"Authorization": f"Bearer {self._admin_token()}"},
        )
        assert r.status_code == 403

    def test_user_token_blocked_on_auditor_route(self, client):
        r = client.get(
            "/auditor/submissions",
            headers={"Authorization": f"Bearer {self._user_token()}"},
        )
        assert r.status_code == 403

    def test_auditor_token_allowed_on_auditor_route(self, client):
        r = client.get(
            "/auditor/submissions",
            headers={"Authorization": f"Bearer {self._auditor_token()}"},
        )
        # 200 (empty list) – auditor is allowed
        assert r.status_code == 200

    def test_disabled_db_auditor_token_rejected(self, client, db):
        a = make_auditor(db, "dis@test.com", "pw", status="disabled")
        token = create_token(sub=a.email, role="auditor", extra={"auditor_id": a.id})
        r = client.get(
            "/auditor/submissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403

    def test_active_db_auditor_token_allowed(self, client, db):
        a = make_auditor(db, "active@test.com", "pw", status="active")
        token = create_token(sub=a.email, role="auditor", extra={"auditor_id": a.id})
        r = client.get(
            "/auditor/submissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Existing /auth/auditor-login still works (non-regression)
# ---------------------------------------------------------------------------

class TestLegacyAuditorLogin:
    def test_old_auditor_login_still_works(self, client):
        r = client.post("/auth/auditor-login", json={
            "username": settings.AUDITOR_ID,
            "password": settings.AUDITOR_PASSWORD,
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        # Legacy endpoint returns AuditorLoginResponse (no 'role' field)
        assert "role" not in data
