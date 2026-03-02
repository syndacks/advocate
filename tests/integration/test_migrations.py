"""Integration tests for Alembic migrations — requires a running Postgres."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

EXPECTED_TABLES = [
    "candidates",
    "cases",
    "evidence_items",
    "artifacts",
    "component_observations",
    "case_state_versions",
    "case_evaluation_runs",
    "evaluation_run_inputs",
    "evaluation_run_producers",
    "prediction_runs",
    "recommended_actions",
    "processing_runs",
    "evaluation_run_outputs",
    "audit_events",
    "retrieval_chunks",
]


@pytest.mark.integration
async def test_all_tables_created(async_engine: AsyncEngine) -> None:
    """All 15 schema tables exist after running migrations."""
    async with async_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        tables = {row[0] for row in result}

    for expected in EXPECTED_TABLES:
        assert expected in tables, f"Table '{expected}' not found after migration"


@pytest.mark.integration
async def test_pgvector_extension_enabled(async_engine: AsyncEngine) -> None:
    """pgvector extension is enabled in the database."""
    async with async_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        )
        row = result.fetchone()

    assert row is not None, "pgvector extension not installed"


@pytest.mark.integration
async def test_case_state_version_unique_constraint(async_engine: AsyncEngine) -> None:
    """case_state_versions has a unique constraint on (case_id, version_number)."""
    async with async_engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'case_state_versions'
                  AND indexdef LIKE '%case_id%version_number%'
            """)
        )
        indexes = [row[0] for row in result]

    assert len(indexes) >= 1, "No unique index on (case_id, version_number) found"


@pytest.mark.integration
async def test_case_evaluation_runs_unique_version_constraint(async_engine: AsyncEngine) -> None:
    """case_evaluation_runs has a unique constraint on case_state_version_id (one manifest per version)."""
    async with async_engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'case_evaluation_runs'
                  AND indexdef LIKE '%case_state_version_id%'
                  AND indexdef LIKE '%UNIQUE%'
            """)
        )
        indexes = [row[0] for row in result]

    assert len(indexes) >= 1, "No unique index on case_state_version_id found"
