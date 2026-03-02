# AGENTS.md

Authoritative guide for coding agents (Claude Code, OpenAI Codex, etc.) working on this repository. Read this before writing any code.

---

## System Overview

This is a local, production-shaped job-search case engine. It is **not** a chatbot or CRM. It is a decision-support system that mirrors disability advocacy platforms. Every target company is a long-lived case. Evidence arrives over time. Processing re-evaluates the case deterministically.

The full architecture is in [architecture.md](architecture.md). The database schema is in [schema.md](schema.md). The implementation phases are in [implementation_plan.md](implementation_plan.md).

---

## Language and Runtime

- **Python 3.11+** only. Use modern syntax (match statements, `X | Y` unions, `typing.Self`).
- **No Python 3.9 compatibility shims.** Do not use `from __future__ import annotations` unless strictly necessary.

---

## Dependency Management

- Use **`pyproject.toml`** for all dependency declarations. Do not edit `requirements_original.txt` (legacy reference only).
- Install with `pip install -e ".[dev]"` or `uv sync`.
- Do **not** add new top-level dependencies without a clear architectural reason.

---

## Key Libraries — Use These, Not Alternatives

| Purpose | Use | Do NOT Use |
|---|---|---|
| HTTP API | `fastapi` + `uvicorn` | Flask, Django, Starlette directly |
| Data validation | `pydantic v2` | marshmallow, attrs, dataclasses alone |
| Settings/config | `pydantic-settings` | raw `os.environ`, python-dotenv alone |
| Database ORM | `sqlalchemy 2.x` (async) | SQLAlchemy sync sessions in async handlers |
| Postgres driver | `asyncpg` | psycopg2 in async context |
| Migrations | `alembic` | Manual SQL files |
| Orchestration | `prefect 2.x` | Celery, RQ, plain threads |
| LLM calls | `openai` SDK directly | `langchain`, `llama-index`, `openai` via langchain wrapper |
| Embeddings | `openai` embeddings API or `sentence-transformers` | Any langchain embedding wrapper |
| Vector search | `pgvector` (via sqlalchemy) | Pinecone, Weaviate, Chroma |
| OCR | `pytesseract` + `pillow` | Any cloud OCR service |
| Testing | `pytest` + `pytest-asyncio` | unittest |
| HTTP test client | `httpx` (async) | `requests` in tests |
| Object storage | `boto3` against local MinIO | Any proprietary storage SDK |

---

## Architecture Invariants — Never Violate These

1. **All intelligence flows through versioned state, never around it.**
   Every recommendation, packet, and score must derive from a `CaseStateVersion`.

2. **Evidence is append-only.**
   Never update or delete `evidence_items`. New interpretations create new `component_observations`.

3. **Every `CaseStateVersion` has exactly one `case_evaluation_run`.**
   Never persist a case state version without first opening and closing an evaluation manifest.

4. **LLMs never mutate state.**
   LLM output is treated as input to the merge engine, not as truth. Invalid JSON from an LLM is a task failure, not a state update.

5. **Per-case advisory locks serialize processing.**
   All `process_case_event` flow runs for the same `case_id` must hold a Postgres advisory lock. Race conditions are bugs.

6. **Deterministic logic owns compliance-grade behavior.**
   Staleness, contradiction detection, action generation, and scoring stay rule-based and versioned. LLMs may rank or draft, never invent or suppress.

7. **Artifacts are never overwritten.**
   New processing always produces new artifact rows with new `artifact_id` values.

8. **The UI reads only from `CaseStateVersion`.**
   No UI logic should read raw `evidence_items`, `artifacts`, or `component_observations` directly and interpret them.

---

## Anti-Patterns — Never Do These

- Do not call LLM APIs from ingestion endpoints.
- Do not run synchronous SQLAlchemy sessions inside `async def` route handlers.
- Do not use `langchain` or any langchain wrapper — use the `openai` SDK directly.
- Do not store ephemeral truth in Redis — Redis is only for coordination and cache.
- Do not put business logic in Alembic migration files.
- Do not create `CaseStateVersion` records without a linked `case_evaluation_run`.
- Do not hardcode model names or prompt strings inline — version them via config.
- Do not use `SELECT *` in repository queries — select named columns.
- Do not skip the architecture diagram update at the end of each phase.

---

## Async Strategy

All I/O must be async end-to-end.

- **FastAPI routes**: always `async def`. Use `asyncpg` via SQLAlchemy async session (`AsyncSession`).
- **SQLAlchemy**: use `create_async_engine` and `AsyncSession` from `sqlalchemy.ext.asyncio`. Never import `Session` (the sync class) in application code.
- **Prefect flows and tasks**: use `@flow` and `@task` decorators. For CPU-bound work (OCR), use `task(task_runner=ThreadPoolTaskRunner())`. For I/O-bound work, use async tasks.
- **Advisory locks**: acquire via raw SQL `SELECT pg_try_advisory_xact_lock($1)` within an `AsyncSession` transaction.
- **Background triggers**: ingestion endpoints dispatch to Prefect via `await flow.run_async(...)` or by sending a message to an in-process queue. Do not use FastAPI `BackgroundTasks` for durable work.

---

## File Structure Conventions

```
src/advocate/
  config.py          # Settings singleton (pydantic-settings)
  domain/            # Pydantic domain models (no DB logic)
  storage/           # SQLAlchemy models + repositories
  ingestion/         # FastAPI router for evidence intake
  processing/        # Prefect flows and tasks
  scoring/           # Rule-based scoring engine
  retrieval/         # Hybrid search (vector + structured)
  rendering/         # Packet templates and PDF rendering
  evaluation/        # Scenario runner and assertion framework
apps/
  api/               # FastAPI app entrypoint
  worker/            # Prefect worker entrypoint
  ui/                # Frontend (framework TBD)
infra/
  migrations/        # Alembic migration files
configs/             # Runtime YAML configs (not secrets)
tests/
  unit/              # Isolated logic (no DB, no network)
  integration/       # Requires running services
  scenarios/         # Full scenario replay tests
    fixtures/        # Scenario YAML + evidence files
```

---

## Testing Rules

1. **Unit tests** cover: merge logic, state machine operators, scoring formulas, action rules. No DB, no network.
2. **Integration tests** cover: storage repositories, API endpoints, Prefect flow execution. Require running Postgres and MinIO.
3. **Scenario tests** cover: full evidence-replay pipelines. Require all services. Scenario fixtures are never visible to prompt templates or retrieval corpora.
4. Mark async tests with `@pytest.mark.asyncio`.
5. Use `httpx.AsyncClient` for FastAPI integration tests.
6. Never use `time.sleep()` in tests — use `asyncio.sleep()` or mock time.

---

## Running the Stack

```bash
make dev-up      # Start all docker services
make migrate     # Run Alembic migrations
make test        # Run full test suite
make test-unit   # Unit tests only (no services needed)
make lint        # ruff + mypy
```

See [Makefile](Makefile) and [docker-compose.yml](docker-compose.yml).

Copy `.env.example` to `.env` and fill in secrets before running.

---

## Provenance and Versioning

Every artifact must record:
- `producer`: the task function name
- `producer_version`: a semver string or git SHA
- `input_hashes`: SHA-256 of all inputs that produced the artifact
- `prompt_version` (for LLM tasks): version string matching a versioned prompt template

Every LLM call must record `model_name` and `prompt_version` in the `evaluation_run_producers` table for the current run.

---

## Architecture Diagram

[docs/architecture_diagram.md](docs/architecture_diagram.md) is a **living deliverable**.

Rules:
- At the end of every phase, mark completed files as `[built]`.
- If a file is renamed or moved, update the diagram in the same commit.
- A phase is not complete until the diagram reflects actual repository state.
- Do not mark a file `[built]` until tests for it pass.
