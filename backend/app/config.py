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
    MAX_UPLOAD_MB: int = 8
    GEOJSON_PATH: str = "data/lok_sabha_constituencies.geojson"

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
