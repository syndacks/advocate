"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str

    # Redis (ephemeral coordination only)
    redis_url: str

    # Object storage (S3-compatible / MinIO)
    s3_endpoint_url: str
    s3_access_key_id: str
    s3_secret_access_key: str
    s3_region: str = "us-east-1"
    s3_bucket: str
    s3_artifacts_bucket: str

    # OpenAI
    openai_api_key: str
    openai_extraction_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # Prefect
    prefect_api_url: str

    # Application
    app_env: str = "development"
    app_version: str = "0.1.0"
    log_level: str = "INFO"

    # API server
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Internal worker endpoint
    worker_base_url: str = "http://localhost:8001"


settings = Settings()  # type: ignore[call-arg]
