from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """All configuration comes from environment variables / backend/.env (never from code)."""

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_prefix="ITSM_", extra="ignore")

    database_url: str = "postgresql+psycopg://localhost:5432/itsm"
    jwt_secret: SecretStr = Field(..., description="HS256 signing key, at least 32 characters")
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = Field(60, ge=5, le=24 * 60)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    sla_check_interval_seconds: int = Field(60, ge=5)
    sla_monitor_enabled: bool = True
    simulate_email_failure: bool = False
    simulate_sms_failure: bool = False
    log_level: str = "INFO"

    @field_validator("jwt_secret")
    @classmethod
    def _secret_long_enough(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("ITSM_JWT_SECRET must be at least 32 characters")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
