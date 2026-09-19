import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import app


def test_health_check_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_url_conversion():
    from app.database import engine

    # Verify engine has pool_pre_ping enabled
    assert engine.pool._pre_ping is True

    # Test postgres:// to postgresql:// conversion logic
    test_urls = [
        ("postgres://user:pass@host:5432/db", "postgresql://user:pass@host:5432/db"),
        ("postgresql://user:pass@host:5432/db", "postgresql://user:pass@host:5432/db"),
        ("sqlite:///./test.db", "sqlite:///./test.db"),
    ]
    for input_url, expected in test_urls:
        res = input_url.replace("postgres://", "postgresql://", 1) if input_url.startswith("postgres://") else input_url
        assert res == expected


def test_cors_origins_dev():
    s = Settings(
        ENVIRONMENT="development",
        FRONTEND_ORIGIN="https://myapp.vercel.app, https://other.com",
    )
    origins = s.cors_origins
    assert "https://myapp.vercel.app" in origins
    assert "https://other.com" in origins
    assert "http://localhost:5173" in origins


def test_cors_origins_prod():
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="super-secret-strong-key-12345",
        ADMIN_PASSWORD="super-admin-strong-pass-12345",
        AUDITOR_PASSWORD="super-auditor-strong-pass-12345",
        FRONTEND_ORIGIN="http://localhost:5173, https://civicquest.onrender.com",
    )
    origins = s.cors_origins
    assert "https://civicquest.onrender.com" in origins
    assert "http://localhost:5173" not in origins


def test_frontend_base_url():
    dev_s = Settings(
        ENVIRONMENT="development",
        FRONTEND_ORIGIN="https://civicquest.onrender.com, http://localhost:5173",
    )
    assert dev_s.frontend_base_url == "http://localhost:5173"

    prod_s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="super-secret-strong-key-12345",
        ADMIN_PASSWORD="super-admin-strong-pass-12345",
        AUDITOR_PASSWORD="super-auditor-strong-pass-12345",
        FRONTEND_ORIGIN="http://localhost:5173, https://civicquest.onrender.com",
    )
    assert prod_s.frontend_base_url == "https://civicquest.onrender.com"


def test_production_refuses_default_or_short_secrets():
    # Test short secret key
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="short",
            ADMIN_PASSWORD="secure-admin-password-123",
            AUDITOR_PASSWORD="secure-auditor-password-123",
        )

    # Test default example secret key
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="dev-secret-key-change-in-production-1234567890",
            ADMIN_PASSWORD="secure-admin-password-123",
            AUDITOR_PASSWORD="secure-auditor-password-123",
        )

    # Test default admin password
    with pytest.raises(ValueError, match="ADMIN_PASSWORD"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="super-secret-key-production-1234",
            ADMIN_PASSWORD="admin@gov",
            AUDITOR_PASSWORD="secure-auditor-password-123",
        )

    # Test default auditor password
    with pytest.raises(ValueError, match="AUDITOR_PASSWORD"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="super-secret-key-production-1234",
            ADMIN_PASSWORD="secure-admin-password-123",
            AUDITOR_PASSWORD="auditor123",
        )


def test_production_builtin_auditor_disabled_by_default():
    # When not explicitly supplied in production, BUILTIN_AUDITOR_ENABLED must be forced False
    prod_s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="super-secret-key-production-1234",
        ADMIN_PASSWORD="secure-admin-password-123",
        AUDITOR_PASSWORD="secure-auditor-password-123",
    )
    assert prod_s.BUILTIN_AUDITOR_ENABLED is False

    # When explicitly set to True in production, it should be True
    prod_s_enabled = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="super-secret-key-production-1234",
        ADMIN_PASSWORD="secure-admin-password-123",
        AUDITOR_PASSWORD="secure-auditor-password-123",
        BUILTIN_AUDITOR_ENABLED=True,
    )
    assert prod_s_enabled.BUILTIN_AUDITOR_ENABLED is True
