from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SECRET_KEY: str = "dev-secret-key-change-in-production-1234567890"
    DATABASE_URL: str = "sqlite:///./app.db"
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    AUDITOR_ID: str = "auditor"
    AUDITOR_PASSWORD: str = "auditor123"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    ALLOWED_EMAIL_DOMAIN: str = "gmail.com"
    XP_PER_APPROVAL: int = 150
    XP_PER_COMPLAINT: int = 50
    MAX_PENDING_COMPLAINTS: int = 3
    MAX_UPLOAD_MB: int = 8
    GEOJSON_PATH: str = "data/lok_sabha_constituencies.geojson"
    ADMIN_ID: str = "civicquest-admin@gov.in"
    ADMIN_PASSWORD: str = "admin@gov"
    INVITE_EXPIRE_HOURS: int = 48
    OTP_EXPIRE_MINUTES: int = 5
    OTP_MAX_ATTEMPTS: int = 5
    RESET_REQUESTS_PER_DAY: int = 2
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCK_MINUTES: int = 15
    LEGACY_OTP_LOGIN_ENABLED: bool = False
    LOCATION_CHANGE_DAYS: int = 30
    BUILTIN_AUDITOR_ENABLED: bool = True

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
