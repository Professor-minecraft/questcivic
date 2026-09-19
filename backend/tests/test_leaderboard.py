"""
Tests for GET /leaderboard
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import User
from app.security import create_token

# ---------------------------------------------------------------------------
# In-memory SQLite database for tests
# ---------------------------------------------------------------------------
TEST_DB_URL = "sqlite:///./test_leaderboard.db"
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
def reset_db():
    """Create a fresh schema before each test, drop after."""
    Base.metadata.create_all(bind=engine)
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


def make_user(db, email: str, xp: int = 0) -> User:
    """Create and persist a test user, return it with a real id."""
    u = User(
        email=email,
        otp_secret="testsecret",
        xp=xp,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def token_for(user: User) -> str:
    return create_token(sub=str(user.id), role="user")


def auditor_token() -> str:
    return create_token(sub="auditor", role="auditor")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLeaderboardAuth:
    def test_no_token_returns_401(self, client):
        r = client.get("/leaderboard")
        assert r.status_code == 401

    def test_auditor_token_returns_403(self, client, db):
        r = client.get(
            "/leaderboard",
            headers={"Authorization": f"Bearer {auditor_token()}"},
        )
        assert r.status_code == 403

    def test_user_token_returns_200(self, client, db):
        u = make_user(db, "user@test.com", xp=10)
        r = client.get(
            "/leaderboard",
            headers={"Authorization": f"Bearer {token_for(u)}"},
        )
        assert r.status_code == 200


class TestLeaderboardRanking:
    def test_highest_xp_is_rank_1(self, client, db):
        top = make_user(db, "alpha@test.com", xp=500)
        make_user(db, "beta@test.com", xp=300)
        make_user(db, "gamma@test.com", xp=100)

        r = client.get(
            "/leaderboard",
            headers={"Authorization": f"Bearer {token_for(top)}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["items"][0]["rank"] == 1
        assert data["items"][0]["xp"] == 500

    def test_equal_xp_shares_rank(self, client, db):
        u1 = make_user(db, "alice@test.com", xp=200)
        u2 = make_user(db, "alison@test.com", xp=200)
        make_user(db, "bob@test.com", xp=100)

        r = client.get(
            "/leaderboard",
            headers={"Authorization": f"Bearer {token_for(u1)}"},
        )
        assert r.status_code == 200
        items = r.json()["items"]
        # Both 200-XP users must have rank 1
        rank1_items = [i for i in items if i["xp"] == 200]
        assert len(rank1_items) == 2
        assert all(i["rank"] == 1 for i in rank1_items)
        # 100-XP user must have rank 3 (2 users ahead)
        rank_of_100 = next(i["rank"] for i in items if i["xp"] == 100)
        assert rank_of_100 == 3

    def test_zero_xp_user_excluded_from_items(self, client, db):
        active = make_user(db, "active@test.com", xp=50)
        make_user(db, "zero@test.com", xp=0)

        r = client.get(
            "/leaderboard",
            headers={"Authorization": f"Bearer {token_for(active)}"},
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert all(i["xp"] > 0 for i in items)
        assert len(items) == 1  # only the 50-XP user

    def test_no_email_or_id_in_response(self, client, db):
        u = make_user(db, "private@test.com", xp=99)
        r = client.get(
            "/leaderboard",
            headers={"Authorization": f"Bearer {token_for(u)}"},
        )
        body = r.text
        assert "private@test.com" not in body
        assert "email" not in body
        # id should not appear as a field name in items
        import json
        data = json.loads(body)
        for item in data["items"]:
            assert "id" not in item
            assert "email" not in item


class TestLeaderboardMasking:
    def test_name_masked_correctly(self, client, db):
        u = make_user(db, "patricia@test.com", xp=10)
        r = client.get(
            "/leaderboard",
            headers={"Authorization": f"Bearer {token_for(u)}"},
        )
        items = r.json()["items"]
        assert items[0]["name"] == "pa***"

    def test_short_email_local_part(self, client, db):
        """Local part with 1 character: use that 1 char + ***"""
        u = make_user(db, "x@test.com", xp=5)
        r = client.get(
            "/leaderboard",
            headers={"Authorization": f"Bearer {token_for(u)}"},
        )
        items = r.json()["items"]
        assert items[0]["name"] == "x***"


class TestLeaderboardIsMe:
    def test_is_me_set_correctly(self, client, db):
        me = make_user(db, "me@test.com", xp=100)
        other = make_user(db, "other@test.com", xp=50)

        r = client.get(
            "/leaderboard",
            headers={"Authorization": f"Bearer {token_for(me)}"},
        )
        items = r.json()["items"]
        me_items = [i for i in items if i["is_me"]]
        other_items = [i for i in items if not i["is_me"]]
        assert len(me_items) == 1
        assert me_items[0]["xp"] == 100
        assert len(other_items) == 1
        assert other_items[0]["xp"] == 50

    def test_me_section_with_xp(self, client, db):
        u = make_user(db, "me@test.com", xp=75)
        r = client.get(
            "/leaderboard",
            headers={"Authorization": f"Bearer {token_for(u)}"},
        )
        me = r.json()["me"]
        assert me["xp"] == 75
        assert me["rank"] == 1

    def test_me_section_zero_xp(self, client, db):
        """User with 0 XP: rank is null, xp is 0."""
        u = make_user(db, "newbie@test.com", xp=0)
        r = client.get(
            "/leaderboard",
            headers={"Authorization": f"Bearer {token_for(u)}"},
        )
        me = r.json()["me"]
        assert me["xp"] == 0
        assert me["rank"] is None


class TestLeaderboardLimit:
    def test_default_limit_20(self, client, db):
        # Create 25 users with xp > 0
        caller = make_user(db, "caller@test.com", xp=1)
        for i in range(25):
            make_user(db, f"user{i:02d}@test.com", xp=i + 2)

        r = client.get(
            "/leaderboard",
            headers={"Authorization": f"Bearer {token_for(caller)}"},
        )
        assert r.status_code == 200
        assert len(r.json()["items"]) == 20

    def test_custom_limit_respected(self, client, db):
        caller = make_user(db, "caller@test.com", xp=1)
        for i in range(10):
            make_user(db, f"u{i}@test.com", xp=i + 2)

        r = client.get(
            "/leaderboard?limit=5",
            headers={"Authorization": f"Bearer {token_for(caller)}"},
        )
        assert len(r.json()["items"]) == 5

    def test_limit_capped_at_50(self, client, db):
        """limit=100 must be rejected (422) because Query cap is 50."""
        caller = make_user(db, "caller@test.com", xp=1)
        r = client.get(
            "/leaderboard?limit=100",
            headers={"Authorization": f"Bearer {token_for(caller)}"},
        )
        assert r.status_code == 422

    def test_sort_order_xp_desc_then_id_asc(self, client, db):
        """When XP is equal, the user with the lower id appears first."""
        u1 = make_user(db, "first@test.com", xp=100)   # id comes first due to insert order
        u2 = make_user(db, "second@test.com", xp=100)
        assert u1.id < u2.id

        r = client.get(
            "/leaderboard",
            headers={"Authorization": f"Bearer {token_for(u1)}"},
        )
        items = r.json()["items"]
        assert items[0]["name"] == "fi***"   # first@ → fi***
        assert items[1]["name"] == "se***"   # second@ → se***
