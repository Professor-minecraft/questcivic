from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
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

    # Storage abstraction settings ("local" or "s3")
    STORAGE_BACKEND: str = "local"
    S3_ENDPOINT_URL: str = ""
    S3_BUCKET: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_REGION: str = "us-east-1"
    S3_PUBLIC_BASE_URL: str = ""

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def frontend_base_url(self) -> str:
        """Returns the primary frontend URL for emails, invites, and redirects."""
        origins = [o.strip().rstrip("/") for o in self.FRONTEND_ORIGIN.split(",") if o.strip()]
        if self.ENVIRONMENT.lower() == "development":
            for o in origins:
                if "5173" in o or "localhost" in o:
                    return o
            return origins[0] if origins else "http://localhost:5173"
        else:
            for o in origins:
                if not (o.startswith("http://localhost") or o.startswith("http://127.0.0.1")):
                    return o
            return origins[0] if origins else "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        """Parsed origins for CORSMiddleware. Localhost is permitted only in development."""
        raw_origins = [o.strip() for o in self.FRONTEND_ORIGIN.split(",") if o.strip()]
        is_dev = self.ENVIRONMENT.lower() == "development"
        origins: list[str] = []
        for origin in raw_origins:
            if not is_dev and (origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1")):
                continue
            if origin not in origins:
                origins.append(origin)
        if is_dev and "http://localhost:5173" not in origins:
            origins.append("http://localhost:5173")
        return origins

    @model_validator(mode="after")
    def validate_production_safeguards(self):
        if self.ENVIRONMENT.lower() == "production":
            # Force BUILTIN_AUDITOR_ENABLED off unless it is explicitly set to True
            if "BUILTIN_AUDITOR_ENABLED" not in self.model_fields_set or not self.BUILTIN_AUDITOR_ENABLED:
                self.BUILTIN_AUDITOR_ENABLED = False

            # Validate SECRET_KEY
            if (
                not self.SECRET_KEY
                or len(self.SECRET_KEY) < 12
                or self.SECRET_KEY.startswith("dev-secret-key")
            ):
                raise ValueError(
                    "In production, SECRET_KEY must be set, at least 12 characters long, "
                    "and not equal to the default/example value."
                )

            # Validate ADMIN_PASSWORD
            if (
                not self.ADMIN_PASSWORD
                or len(self.ADMIN_PASSWORD) < 12
                or self.ADMIN_PASSWORD in ("admin@gov", "admin", "admin123")
            ):
                raise ValueError(
                    "In production, ADMIN_PASSWORD must be set, at least 12 characters long, "
                    "and not equal to the default/example value."
                )

            # Validate AUDITOR_PASSWORD
            if (
                not self.AUDITOR_PASSWORD
                or len(self.AUDITOR_PASSWORD) < 12
                or self.AUDITOR_PASSWORD in ("auditor123", "aud", "auditor")
            ):
                raise ValueError(
                    "In production, AUDITOR_PASSWORD must be set, at least 12 characters long, "
                    "and not equal to the default/example value."
                )

            # Validate S3 configuration if STORAGE_BACKEND is s3
            if self.STORAGE_BACKEND.lower() == "s3":
                missing = []
                for field in ("S3_ENDPOINT_URL", "S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY", "S3_PUBLIC_BASE_URL"):
                    val = getattr(self, field, "")
                    if not val or "CHANGE_ME" in val:
                        missing.append(field)
                if missing:
                    raise ValueError(
                        f"In production with STORAGE_BACKEND=s3, the following S3 variables must be set: {', '.join(missing)}"
                    )
        return self


settings = Settings()
