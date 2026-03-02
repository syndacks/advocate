"""Shared pytest fixtures for all test layers.

Unit tests: use only `settings` (no infrastructure).
Integration tests: use `async_engine`, `async_db_session`, and `test_client`
  — these require a running Postgres (started via `make dev-up`).
"""

import os
import subprocess
import sys
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import boto3
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from advocate.domain.models import CandidateCreate, CaseCreate
from advocate.storage.repositories import insert_candidate, insert_case

_STUB_ENV: dict[str, str] = {
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


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: marks tests as requiring live infrastructure (Postgres, MinIO, Prefect)",
    )
    # Set stub env vars before any module-level Settings() call so collection succeeds.
    # Individual tests may override these with monkeypatch.
    for key, value in _STUB_ENV.items():
        os.environ.setdefault(key, value)


@pytest.fixture(scope="session")
def db_url() -> str:
    """Database URL for tests. Prefers TEST_DATABASE_URL, falls back to DATABASE_URL."""
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("No DATABASE_URL set — skipping integration test")
    return url


@pytest.fixture(scope="session")
def _run_migrations(db_url: str) -> None:
    """Run alembic migrations once per session (sync, via subprocess)."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        env={**os.environ, "DATABASE_URL": db_url},
    )
    if result.returncode != 0:
        pytest.fail(f"alembic upgrade head failed:\n{result.stderr}")


@pytest_asyncio.fixture
async def async_engine(db_url: str, _run_migrations: None) -> AsyncEngine:  # type: ignore[misc]
    """Function-scoped async engine. Disposes after each test to avoid loop conflicts."""
    engine = create_async_engine(db_url, echo=False, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_db_session(async_engine: AsyncEngine) -> AsyncSession:  # type: ignore[misc]
    """Function-scoped async DB session. Rolls back after each test."""
    async_session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session_factory() as session:
        yield session
        if session.in_transaction():
            await session.rollback()


@pytest_asyncio.fixture
async def test_client() -> AsyncClient:  # type: ignore[misc]
    """AsyncClient wrapping the FastAPI app for integration tests."""
    from apps.api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
def minio_client() -> object:
    """Boto3 S3 client for MinIO read-back assertions."""
    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("S3_REGION", "us-east-1"),
    )


@pytest_asyncio.fixture
async def create_candidate_and_case(
    async_db_session: AsyncSession,
) -> Callable[[], Awaitable[tuple[UUID, UUID]]]:
    """Create a committed candidate and case for API integration tests."""

    async def _create() -> tuple[UUID, UUID]:
        candidate = await insert_candidate(
            async_db_session,
            CandidateCreate(
                full_name="Alex Rivera",
                primary_email=f"alex+{uuid4()}@example.com",
                target_comp_min=140000,
                target_comp_max=180000,
            ),
        )
        case = await insert_case(
            async_db_session,
            CaseCreate(
                candidate_id=candidate.candidate_id,
                company_name=f"ExampleCo-{uuid4()}",
                role_title="Senior Product Manager",
                source_channel="manual_ui",
                metadata_json={"origin": "test"},
            ),
        )
        await async_db_session.commit()
        return candidate.candidate_id, case.case_id

    return _create


@pytest_asyncio.fixture
async def ensure_process_case_event_deployment() -> UUID:
    """Ensure the Phase 2 Prefect deployment exists before dispatch tests run."""
    from apps.worker.main import ensure_process_case_event_deployment as ensure_deployment

    return await ensure_deployment()
