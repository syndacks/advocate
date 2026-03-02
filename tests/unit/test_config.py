"""Smoke tests for config loading — no infrastructure required."""

import pytest
from pydantic import ValidationError

from advocate.config import Settings

REQUIRED_ENV_VARS = {
    "DATABASE_URL": "postgresql+asyncpg://advocate:advocate@localhost:5433/advocate_app",
    "REDIS_URL": "redis://localhost:6379/0",
    "S3_ENDPOINT_URL": "http://localhost:9000",
    "S3_ACCESS_KEY_ID": "minioadmin",
    "S3_SECRET_ACCESS_KEY": "minioadmin",
    "S3_BUCKET": "advocate-evidence",
    "S3_ARTIFACTS_BUCKET": "advocate-artifacts",
    "OPENAI_API_KEY": "sk-test",
    "OPENAI_EXTRACTION_MODEL": "gpt-4o-mini",
    "OPENAI_EMBEDDING_MODEL": "text-embedding-3-small",
    "PREFECT_API_URL": "http://localhost:4200/api",
    "APP_ENV": "test",
    "APP_VERSION": "0.1.0",
    "LOG_LEVEL": "INFO",
}


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings loads without error when all required env vars are set."""
    for key, value in REQUIRED_ENV_VARS.items():
        monkeypatch.setenv(key, value)

    settings = Settings()

    assert settings.database_url == REQUIRED_ENV_VARS["DATABASE_URL"]
    assert settings.redis_url == REQUIRED_ENV_VARS["REDIS_URL"]
    assert settings.app_env == "test"
    assert settings.app_version == "0.1.0"


def test_settings_exposes_s3_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings exposes all S3/MinIO fields."""
    for key, value in REQUIRED_ENV_VARS.items():
        monkeypatch.setenv(key, value)

    settings = Settings()

    assert settings.s3_endpoint_url == "http://localhost:9000"
    assert settings.s3_bucket == "advocate-evidence"
    assert settings.s3_artifacts_bucket == "advocate-artifacts"


def test_settings_missing_required_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings raises ValidationError when a required field is missing."""
    for key, value in REQUIRED_ENV_VARS.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings()
