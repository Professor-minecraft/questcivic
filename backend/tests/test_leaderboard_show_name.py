"""
Tests for user full name on the leaderboard and signup name validation.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import User
from app.security import create_token
from tests.test_leaderboard import Base, engine, TestingSessionLocal


@pytest.fixture(autouse=True)
def reset_db():
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


def make_user(db, email: str, name: str = None, xp: int = 0) -> User:
    u = User(
        email=email,
        name=name,
        otp_secret="testsecret",
        xp=xp,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def token_for(user: User) -> str:
    return create_token(sub=str(user.id), role="user")


class TestSignupNameValidation:
    def test_valid_names(self, client):
        # Letters, spaces, dots, hyphens, apostrophes, international letters
        valid_cases = [
            "Jane Doe",
            "  Jean-Luc  D'Souza. ",
            "Dr. J. Smith-Jones",
            "René François",
            "मृणय पाटील",
            "Al",
            "A" * 60,
        ]
        for name in valid_cases:
            r = client.post(
                "/auth/signup",
                json={
                    "name": name,
                    "email": f"valid_{abs(hash(name))}@gmail.com",
                    "password": "Password123",
                },
            )
            # Should accept the name (returns 200 OTP sent)
            assert r.status_code == 200, f"Expected 200 for name '{name}', got {r.status_code}: {r.text}"

    def test_rejected_html_tag_name(self, client):
        r = client.post(
            "/auth/signup",
            json={
                "name": "<b>x</b>",
                "email": "test1@gmail.com",
                "password": "Password123",
            },
        )
        assert r.status_code == 400
        assert "letters, spaces, dots, hyphens, and apostrophes" in r.json()["detail"]

    def test_rejected_numeric_name(self, client):
        r = client.post(
            "/auth/signup",
            json={
                "name": "12345",
                "email": "test2@gmail.com",
                "password": "Password123",
            },
        )
        assert r.status_code == 400

    def test_rejected_too_short_or_too_long(self, client):
        r_short = client.post(
            "/auth/signup",
            json={
                "name": "A",
                "email": "short@gmail.com",
                "password": "Password123",
            },
        )
        assert r_short.status_code == 400
        assert "between 2 and 60" in r_short.json()["detail"]

        r_long = client.post(
            "/auth/signup",
            json={
                "name": "A" * 61,
                "email": "long@gmail.com",
                "password": "Password123",
            },
        )
        assert r_long.status_code == 400
        assert "between 2 and 60" in r_long.json()["detail"]

    def test_rejected_special_characters_no_letters(self, client):
        for bad_name in ["...", "---", "   ", "user@host", "Alice #1"]:
            r = client.post(
                "/auth/signup",
                json={
                    "name": bad_name,
                    "email": "bad@gmail.com",
                    "password": "Password123",
                },
            )
            assert r.status_code == 400, f"Expected 400 for '{bad_name}', got {r.status_code}"


class TestLeaderboardNameFormatting:
    def test_user_with_name_shows_full_name(self, client, db):
        u = make_user(db, "alice@gmail.com", name="  Alice   Wonderland  ", xp=50)
        r = client.get("/leaderboard", headers={"Authorization": f"Bearer {token_for(u)}"})
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["name"] == "Alice Wonderland"

    def test_old_user_with_no_name_shows_masked_email(self, client, db):
        u = make_user(db, "patricia@gmail.com", name=None, xp=30)
        r = client.get("/leaderboard", headers={"Authorization": f"Bearer {token_for(u)}"})
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["name"] == "pa***"

    def test_response_never_contains_email_or_id(self, client, db):
        u = make_user(db, "secret_person@gmail.com", name="Secret Agent", xp=100)
        r = client.get("/leaderboard", headers={"Authorization": f"Bearer {token_for(u)}"})
        assert r.status_code == 200
        raw_text = r.text
        assert "secret_person@gmail.com" not in raw_text
        data = r.json()
        for item in data["items"]:
            assert "email" not in item
            assert "id" not in item
            assert set(item.keys()) == {"rank", "name", "xp", "is_me"}
        assert set(data["me"].keys()) == {"rank", "xp"}

    def test_legacy_show_name_zero_is_ignored(self, client, db):
        u = make_user(db, "bob@gmail.com", name="Bob Builder", xp=40)
        u.show_name = 0
        db.commit()
        r = client.get("/leaderboard", headers={"Authorization": f"Bearer {token_for(u)}"})
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["name"] == "Bob Builder"

    def test_me_response_has_no_show_name(self, client, db):
        u = make_user(db, "me_user@gmail.com", name="Me User", xp=10)
        r = client.get("/me", headers={"Authorization": f"Bearer {token_for(u)}"})
        assert r.status_code == 200
        data = r.json()
        assert "show_name" not in data

    def test_visibility_route_is_gone(self, client, db):
        u = make_user(db, "vis_user@gmail.com", name="Vis User", xp=10)
        r = client.put(
            "/me/leaderboard-visibility",
            json={"show_name": False},
            headers={"Authorization": f"Bearer {token_for(u)}"},
        )
        assert r.status_code == 404
