import logging
from unittest.mock import MagicMock, patch
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, settings
from app.database import Base, get_db
from app.main import app
from app.models import OTPRequest, PendingSignup, User
from app.services.email_sender import send_email, send_otp
from app.services.invite_email import send_invite_email
from app.services.reset_email import send_password_changed_notice, send_password_reset_email


# In-memory SQLite fixture for signup rollback tests
@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestingSessionLocal
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)


# =========================================================================
# 1. Configuration Validation Tests
# =========================================================================

def test_email_backend_validation():
    # Valid backends
    for b in ("smtp", "brevo", "resend", "SMTP", "Brevo", "Resend"):
        s = Settings(EMAIL_BACKEND=b)
        assert s.EMAIL_BACKEND == b

    # Invalid backend
    with pytest.raises(ValueError, match="Invalid EMAIL_BACKEND"):
        Settings(EMAIL_BACKEND="sendgrid")


def test_production_email_safeguards():
    # In production, brevo requires EMAIL_API_KEY and EMAIL_FROM_ADDRESS
    with pytest.raises(ValueError, match="EMAIL_API_KEY"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="super-secret-production-key-1234",
            ADMIN_PASSWORD="super-admin-password-123",
            AUDITOR_PASSWORD="super-auditor-password-123",
            EMAIL_BACKEND="brevo",
            EMAIL_API_KEY="",
            EMAIL_FROM_ADDRESS="noreply@domain.com",
        )

    with pytest.raises(ValueError, match="EMAIL_FROM_ADDRESS"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="super-secret-production-key-1234",
            ADMIN_PASSWORD="super-admin-password-123",
            AUDITOR_PASSWORD="super-auditor-password-123",
            EMAIL_BACKEND="resend",
            EMAIL_API_KEY="re_testkey123",
            EMAIL_FROM_ADDRESS="",
        )

    # Valid production config with resend
    prod_s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="super-secret-production-key-1234",
        ADMIN_PASSWORD="super-admin-password-123",
        AUDITOR_PASSWORD="super-auditor-password-123",
        EMAIL_BACKEND="resend",
        EMAIL_API_KEY="re_testkey123456",
        EMAIL_FROM_ADDRESS="noreply@domain.com",
    )
    assert prod_s.EMAIL_BACKEND == "resend"


# =========================================================================
# 2. Brevo Backend Tests
# =========================================================================

def test_brevo_send_success(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_BACKEND", "brevo")
    monkeypatch.setattr(settings, "EMAIL_API_KEY", "xkeysib-test-12345")
    monkeypatch.setattr(settings, "EMAIL_FROM_ADDRESS", "sender@domain.com")
    monkeypatch.setattr(settings, "EMAIL_FROM_NAME", "CivicQuest Test")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 201

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        send_email("recipient@domain.com", "Test Subject", "Hello World")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.brevo.com/v3/smtp/email"
        assert kwargs["headers"]["api-key"] == "xkeysib-test-12345"
        assert kwargs["json"]["sender"] == {"name": "CivicQuest Test", "email": "sender@domain.com"}
        assert kwargs["json"]["to"] == [{"email": "recipient@domain.com"}]
        assert kwargs["json"]["subject"] == "Test Subject"
        assert kwargs["json"]["textContent"] == "Hello World"


def test_brevo_error_response_returns_502_and_sanitizes_logs(monkeypatch, caplog):
    monkeypatch.setattr(settings, "EMAIL_BACKEND", "brevo")
    monkeypatch.setattr(settings, "EMAIL_API_KEY", "xkeysib-supersecret-api-key")
    monkeypatch.setattr(settings, "EMAIL_FROM_ADDRESS", "sender@domain.com")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 401
    mock_resp.text = '{"message": "Key not authorized xkeysib-supersecret-api-key"}'

    with patch("httpx.Client.post", return_value=mock_resp):
        with caplog.at_level(logging.ERROR):
            with pytest.raises(HTTPException) as exc_info:
                send_email("recipient@domain.com", "Test", "Body")
            assert exc_info.value.status_code == 502

        # Verify logs do NOT contain the API key
        for record in caplog.records:
            assert "xkeysib-supersecret-api-key" not in record.message
            assert "[REDACTED]" in record.message or "Key not authorized" in record.message


def test_brevo_timeout_returns_502(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_BACKEND", "brevo")
    monkeypatch.setattr(settings, "EMAIL_API_KEY", "xkeysib-test-12345")
    monkeypatch.setattr(settings, "EMAIL_FROM_ADDRESS", "sender@domain.com")

    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Request timed out")):
        with pytest.raises(HTTPException) as exc_info:
            send_email("recipient@domain.com", "Test", "Body")
        assert exc_info.value.status_code == 502


def test_brevo_network_error_returns_502(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_BACKEND", "brevo")
    monkeypatch.setattr(settings, "EMAIL_API_KEY", "xkeysib-test-12345")
    monkeypatch.setattr(settings, "EMAIL_FROM_ADDRESS", "sender@domain.com")

    with patch("httpx.Client.post", side_effect=httpx.ConnectError("Network unreachable")):
        with pytest.raises(HTTPException) as exc_info:
            send_email("recipient@domain.com", "Test", "Body")
        assert exc_info.value.status_code == 502


# =========================================================================
# 3. Resend Backend Tests
# =========================================================================

def test_resend_send_success(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_BACKEND", "resend")
    monkeypatch.setattr(settings, "EMAIL_API_KEY", "re_secret_test_key")
    monkeypatch.setattr(settings, "EMAIL_FROM_ADDRESS", "sender@domain.com")
    monkeypatch.setattr(settings, "EMAIL_FROM_NAME", "CivicQuest")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        send_email("recipient@domain.com", "Test Subject", "Hello World")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.resend.com/emails"
        assert kwargs["headers"]["Authorization"] == "Bearer re_secret_test_key"
        assert kwargs["json"]["from"] == "CivicQuest <sender@domain.com>"
        assert kwargs["json"]["to"] == ["recipient@domain.com"]
        assert kwargs["json"]["subject"] == "Test Subject"
        assert kwargs["json"]["text"] == "Hello World"


def test_resend_error_response_returns_502_and_sanitizes_logs(monkeypatch, caplog):
    monkeypatch.setattr(settings, "EMAIL_BACKEND", "resend")
    monkeypatch.setattr(settings, "EMAIL_API_KEY", "re_my_secret_token_123")
    monkeypatch.setattr(settings, "EMAIL_FROM_ADDRESS", "sender@domain.com")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 403
    mock_resp.text = '{"message": "Forbidden access re_my_secret_token_123"}'

    with patch("httpx.Client.post", return_value=mock_resp):
        with caplog.at_level(logging.ERROR):
            with pytest.raises(HTTPException) as exc_info:
                send_email("recipient@domain.com", "Test", "Body")
            assert exc_info.value.status_code == 502

        for record in caplog.records:
            assert "re_my_secret_token_123" not in record.message
            assert "[REDACTED]" in record.message or "Forbidden access" in record.message


def test_resend_timeout_and_network_error(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_BACKEND", "resend")
    monkeypatch.setattr(settings, "EMAIL_API_KEY", "re_test")
    monkeypatch.setattr(settings, "EMAIL_FROM_ADDRESS", "sender@domain.com")

    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("timeout")):
        with pytest.raises(HTTPException) as exc_info:
            send_email("recipient@domain.com", "Test", "Body")
        assert exc_info.value.status_code == 502

    with patch("httpx.Client.post", side_effect=httpx.ConnectError("unreachable")):
        with pytest.raises(HTTPException) as exc_info:
            send_email("recipient@domain.com", "Test", "Body")
        assert exc_info.value.status_code == 502


# =========================================================================
# 4. SMTP Backend & Error Handling Tests
# =========================================================================

def test_smtp_network_unreachable_raises_502(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_BACKEND", "smtp")
    monkeypatch.setattr(settings, "SMTP_USER", "user@gmail.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "secretpass")

    with patch("smtplib.SMTP", side_effect=OSError(101, "Network is unreachable")):
        with pytest.raises(HTTPException) as exc_info:
            send_email("recipient@domain.com", "Test", "Body")
        assert exc_info.value.status_code == 502


# =========================================================================
# 5. Unified Sender Dispatcher Tests
# =========================================================================

def test_all_email_paths_route_through_send_email(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_BACKEND", "resend")
    monkeypatch.setattr(settings, "EMAIL_API_KEY", "re_key")
    monkeypatch.setattr(settings, "EMAIL_FROM_ADDRESS", "sender@domain.com")

    with patch("app.services.email_sender.send_email") as mock_send:
        send_otp("user@gmail.com", "123456")
        assert mock_send.call_count == 1
        assert "123456" in mock_send.call_args[0][2]

    with patch("app.services.reset_email.send_email") as mock_send:
        send_password_reset_email("user@gmail.com", "654321")
        assert mock_send.call_count == 1
        assert "654321" in mock_send.call_args[0][2]

    with patch("app.services.reset_email.send_email") as mock_send:
        send_password_changed_notice("user@gmail.com")
        assert mock_send.call_count == 1

    with patch("app.services.invite_email.send_email") as mock_send:
        ok = send_invite_email("auditor@gmail.com", "invite_tok_123")
        assert ok is True
        assert mock_send.call_count == 1
        assert "invite_tok_123" in mock_send.call_args[0][2]

    with patch("app.services.invite_email.send_email", side_effect=HTTPException(status_code=502)):
        fail = send_invite_email("auditor@gmail.com", "invite_tok_123")
        assert fail is False


# =========================================================================
# 6. Signup Endpoint Transactional Rollback Tests
# =========================================================================

def test_signup_email_failure_rolls_back_and_allows_immediate_retry(test_db):
    client = TestClient(app)
    signup_payload = {
        "name": "Arjun Sharma",
        "email": "arjun.sharma@gmail.com",
        "password": "StrongPassword123!",
    }

    # 1) When send_otp fails with 502
    with patch("app.routers.signup.send_otp", side_effect=HTTPException(status_code=502, detail="Failed to send email")):
        res = client.post("/auth/signup", json=signup_payload)
        assert res.status_code == 502
        assert "Failed to send email" in res.json()["detail"]

    # Verify no pending signup was committed
    db = test_db()
    try:
        pending = db.query(PendingSignup).filter(PendingSignup.email == "arjun.sharma@gmail.com").first()
        assert pending is None

        # Verify no OTP request was committed
        otp_req = db.query(OTPRequest).filter(OTPRequest.email == "arjun.sharma@gmail.com").first()
        assert otp_req is None
    finally:
        db.close()

    # 2) Immediate retry with the same email must NOT hit the 60s cooldown or conflict
    with patch("app.routers.signup.send_otp") as mock_otp:
        retry_res = client.post("/auth/signup", json=signup_payload)
        assert retry_res.status_code == 200
        assert retry_res.json() == {"message": "OTP sent"}
        assert mock_otp.call_count == 1

    # Verify it now exists after successful send
    db = test_db()
    try:
        pending = db.query(PendingSignup).filter(PendingSignup.email == "arjun.sharma@gmail.com").first()
        assert pending is not None
        assert pending.name == "Arjun Sharma"
        otp_req = db.query(OTPRequest).filter(OTPRequest.email == "arjun.sharma@gmail.com").first()
        assert otp_req is not None
    finally:
        db.close()


def test_signup_resend_otp_failure_rolls_back(test_db):
    client = TestClient(app)
    # First sign up successfully
    with patch("app.routers.signup.send_otp"):
        res = client.post("/auth/signup", json={
            "name": "Priya Patel",
            "email": "priya.patel@gmail.com",
            "password": "StrongPassword123!",
        })
        assert res.status_code == 200

    db = test_db()
    initial_count = db.query(OTPRequest).filter(OTPRequest.email == "priya.patel@gmail.com").count()
    db.close()
    assert initial_count == 1

    # Now attempt resend-otp with mock failure (after bypassing rate limit cooldown in mock if needed)
    with patch("app.routers.signup.check_otp_rate_limits"):
        with patch("app.routers.signup.send_otp", side_effect=HTTPException(status_code=502)):
            resend_res = client.post("/auth/signup/resend-otp", json={"email": "priya.patel@gmail.com"})
            assert resend_res.status_code == 502

    db = test_db()
    after_count = db.query(OTPRequest).filter(OTPRequest.email == "priya.patel@gmail.com").count()
    db.close()
    assert after_count == initial_count  # No phantom uncommitted record left behind


# =========================================================================
# 7. Password Reset Endpoint Rollback Tests
# =========================================================================

def test_password_reset_email_failure_rolls_back(test_db):
    client = TestClient(app)
    # Create verified user in test database
    db = test_db()
    user = User(
        email="reset.user@gmail.com",
        name="Reset User",
        otp_secret="JBSWY3DPEHPK3PXP",
        password_hash="fakehash123",
        email_verified=1,
    )
    db.add(user)
    db.commit()
    db.close()

    # Request password reset with email failure
    with patch("app.routers.password_reset.send_password_reset_email", side_effect=HTTPException(status_code=502)):
        res = client.post("/auth/forgot-password", json={"email": "reset.user@gmail.com"})
        assert res.status_code == 502

    # Verify no OTPRequest was committed, so daily count is not decremented
    db = test_db()
    count = db.query(OTPRequest).filter(OTPRequest.email == "reset.user@gmail.com").count()
    db.close()
    assert count == 0
