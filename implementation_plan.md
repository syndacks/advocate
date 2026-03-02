# Implementation Plan

## 1. Goal

Build the first usable version of the Advocate-style job-search case engine in phases that preserve the architectural invariants and produce a working system early.

## 2. Delivery Strategy

Build from durable truth outward:

1. storage and schema
2. ingestion and replay
3. deterministic case state
4. bounded extraction
5. scoring and actions
6. rendering and UI
7. evaluation harness

Do not start with chat, agent loops, or prompt-heavy flows.

## 3. Test-First Delivery Rule

Every phase must be implemented with TDD.

Rules:

1. Start each phase by writing the smallest failing tests that express that phase's acceptance criteria.
2. Prefer unit tests over integration tests when a behavior can be isolated deterministically.
3. Add only the thinnest integration layer needed to prove the boundary between components.
4. Add or update scenario coverage only when a user-visible behavior spans multiple layers.
5. Do not write broad end-to-end tests when a narrower test would prove the same behavior.

Thin test layering for this repo:

- unit tests prove merge logic, rule semantics, and scoring
- integration tests prove storage, API, worker, and rendering boundaries
- scenario tests prove full case behavior over time

Scenario direction is defined in [specs/scenario_vision.md](/Users/dacks/repos/advocate/specs/scenario_vision.md).

## 4. Architecture Diagram Rule

[docs/architecture_diagram.md](/Users/dacks/repos/advocate/docs/architecture_diagram.md) is a living deliverable.

The diagram is kept at **subsystem level** — one box per package or service, not one box per file. File-level detail lives in the phase log table, not in the mermaid graph.

Rules:

1. The system diagram shows subsystems and data flow arrows. Do not add individual files to it.
2. At the end of each phase, update the phase log table: change the row status from `planned` to `built` and update the key files list to reflect what was actually built.
3. Add a numbered phase notes section if the implementation diverged from the plan.
4. A phase is not complete until the phase log row is marked `built`.

## 5. Phases

### Phase 0: Repo Bootstrap

Deliverables:

- repository scaffold from [schema.md](/Users/dacks/repos/advocate/schema.md)
- base Python project and dependency management
- local docker services for Postgres, object storage, Redis, and Prefect
- environment template and config loading
- update the phase log in docs/architecture_diagram.md

Key files to create:
- `pyproject.toml` — all dependencies, pytest config, ruff/mypy config
- `docker-compose.yml` — postgres+pgvector, redis, minio, prefect-server
- `.env.example` — all required environment variable names and example values
- `Makefile` — `dev-up`, `migrate`, `test`, `test-unit`, `lint` targets
- `src/advocate/config.py` — `class Settings(BaseSettings)` with all env vars, exported as `settings = Settings()`
- `infra/migrations/env.py` — Alembic async migration environment
- `infra/migrations/versions/` — first migration: create all tables from schema.md
- `tests/conftest.py` — pytest fixtures for async DB session and test client

Key interfaces:
```python
# src/advocate/config.py
class Settings(BaseSettings):
    database_url: str
    redis_url: str
    s3_endpoint_url: str
    s3_access_key_id: str
    s3_secret_access_key: str
    s3_bucket: str
    s3_artifacts_bucket: str
    openai_api_key: str
    openai_extraction_model: str
    openai_embedding_model: str
    prefect_api_url: str
    app_env: str
    app_version: str
    log_level: str

settings = Settings()
```

Acceptance criteria:

- app services boot locally
- database migrations run successfully
- object storage bucket is reachable
- Prefect can execute a no-op flow

TDD slice:

- one smoke test for config loading
- one migration test against a local Postgres instance
- one worker boot test proving a no-op Prefect flow can run

### Phase 1: Core Data Layer

Deliverables:

- migrations for core tables
- typed domain models for `Candidate`, `Case`, `EvidenceItem`, `Artifact`, `CaseStateVersion`
- typed domain models for evaluation provenance tables
- repository layer for append-only inserts and latest-state reads
- audit event writer
- update the phase log in docs/architecture_diagram.md

Key files to create:
- `src/advocate/domain/models.py` — Pydantic v2 domain models (no DB logic)
- `src/advocate/storage/db.py` — `create_async_engine`, `AsyncSession` factory, `get_session` dependency
- `src/advocate/storage/orm.py` — SQLAlchemy ORM mapped classes (mirrors schema.md tables)
- `src/advocate/storage/repositories.py` — repository functions for each entity
- `src/advocate/storage/audit.py` — `write_audit_event(session, event_type, ref_id, payload)`

Key interfaces:
```python
# src/advocate/storage/repositories.py
async def insert_candidate(session: AsyncSession, candidate: Candidate) -> UUID: ...
async def insert_case(session: AsyncSession, case: Case) -> UUID: ...
async def insert_evidence(session: AsyncSession, item: EvidenceItem) -> UUID: ...
async def insert_artifact(session: AsyncSession, artifact: Artifact) -> UUID: ...
async def insert_case_state_version(session: AsyncSession, version: CaseStateVersion) -> UUID: ...
async def get_latest_case_state(session: AsyncSession, case_id: UUID) -> CaseStateVersion | None: ...
async def insert_evaluation_run(session: AsyncSession, run: CaseEvaluationRun) -> UUID: ...
async def get_evaluation_run_for_version(session: AsyncSession, version_id: UUID) -> CaseEvaluationRun: ...
```

Acceptance criteria:

- can create a candidate and case
- can insert evidence and artifacts
- can persist and retrieve a case state version by `case_id`
- can persist and retrieve an evaluation manifest for a case state version
- uniqueness and append-only constraints are enforced

TDD slice:

- unit tests for domain models and invariants
- repository integration tests for append-only writes and latest-state reads
- one constraint test proving duplicate `content_hash` values are allowed
- one repository test proving each `CaseStateVersion` has exactly one evaluation manifest

### Phase 2: Ingestion Service

Deliverables:

- `POST /cases/{case_id}/evidence`
- file upload handling to object storage
- content hashing
- `evidence.received` event emission
- timeline retrieval endpoints
- update the phase log in docs/architecture_diagram.md

Key files to create:
- `src/advocate/ingestion/router.py` — FastAPI router with evidence endpoints
- `src/advocate/ingestion/storage.py` — `upload_blob(bucket, key, data) -> str` using boto3
- `src/advocate/ingestion/hashing.py` — `content_hash(data: bytes) -> str` (SHA-256)
- `src/advocate/ingestion/events.py` — `emit_evidence_received(case_id, evidence_id)` dispatches to Prefect
- `apps/api/main.py` — FastAPI app entrypoint, registers routers

Key interfaces:
```python
# POST /cases/{case_id}/evidence
# Request: multipart/form-data with file + metadata fields
# Response: {"evidence_id": "<uuid>", "case_id": "<uuid>", "received_at": "<iso8601>"}

# GET /cases/{case_id}/timeline
# Response: list of evidence items ordered by received_at ASC

# GET /cases/{case_id}/state/latest
# Response: CaseStateVersion JSON or 404
```

Acceptance criteria:

- uploading a PDF, email text, or note returns an `evidence_id`
- raw payload lands in object storage before the API returns
- duplicate uploads do not corrupt state
- UI can list evidence for a case in arrival order

TDD slice:

- request validation tests for `POST /cases/{case_id}/evidence`
- integration tests for blob write then evidence row insert
- one timeline query test ordered by `received_at`

### Phase 3: Prefect Processing Flow

Deliverables:

- `process_case_event(case_id, evidence_id)`
- per-case advisory lock
- deterministic evidence inspection task
- processing run tracking
- evaluation manifest open and close behavior
- idempotent retry behavior
- update the phase log in docs/architecture_diagram.md

Key files to create:
- `src/advocate/processing/flows.py` — `@flow process_case_event(case_id: UUID, evidence_id: UUID)`
- `src/advocate/processing/locks.py` — `acquire_case_lock(session, case_id)` using pg advisory lock
- `src/advocate/processing/inspect.py` — `@task inspect_evidence(evidence_item) -> EvidenceInspection`
- `src/advocate/processing/manifest.py` — `open_evaluation_run(...)` and `close_evaluation_run(...)`
- `apps/worker/main.py` — Prefect worker entrypoint, registers deployments

Note: `processing_runs` table (defined in schema.md) is written here. One row per flow execution, linked to `case_evaluation_runs`.

Key interfaces:
```python
# src/advocate/processing/flows.py
@flow(name="process-case-event")
async def process_case_event(case_id: UUID, evidence_id: UUID) -> None: ...

# src/advocate/processing/inspect.py
@dataclass
class EvidenceInspection:
    evidence_id: UUID
    evidence_category: Literal["scanned_document", "structured", "free_text", "image", "transcript", "duplicate"]
    requires_ocr: bool
    cache_hit: bool
    artifact_id: UUID | None  # if cache_hit
```

Acceptance criteria:

- new evidence triggers a flow run
- repeated execution for the same evidence does not create inconsistent state
- concurrent evidence for different cases processes independently
- concurrent evidence for the same case is serialized
- a completed flow leaves behind a traceable evaluation manifest

TDD slice:

- unit tests for evidence inspection routing
- integration tests for lock behavior and idempotent reprocessing
- one worker-level test proving the flow records `processing_runs`
- one worker-level test proving the flow records an evaluation manifest with trigger evidence and app version

### Phase 4: Deterministic Merge And Case State

Deliverables:

- parser for [case_requirements.yaml](/Users/dacks/repos/advocate/case_requirements.yaml)
- parser for [specs/state_machine.md](/Users/dacks/repos/advocate/specs/state_machine.md) operator set
- component observation model
- merge engine that materializes `CaseStateVersion`
- completion, staleness, contradiction, and stage computation
- evaluation input and output binding for state materialization
- update the phase log in docs/architecture_diagram.md

Key files to create:
- `src/advocate/domain/requirements.py` — `load_requirements(path) -> CaseRequirements` parser for case_requirements.yaml
- `src/advocate/domain/observations.py` — Pydantic models for each `component_observations.value_json` schema (from specs/observations.md)
- `src/advocate/processing/merge.py` — `merge_observations_into_state(observations, prior_state, requirements, eval_at) -> CaseStateVersion`
- `src/advocate/processing/state_machine.py` — operator implementations: `completion_ratio_lt`, `completed_components_all`, `stale_components_any`, `contradictions_any`, etc.
- `src/advocate/processing/contradictions.py` — `detect_contradictions(observations, rules) -> list[ContradictionFlag]`
- `src/advocate/processing/actions.py` — `generate_actions(state, requirements) -> list[RecommendedAction]`

Key interfaces:
```python
# src/advocate/processing/merge.py
def merge_observations_into_state(
    observations: list[ComponentObservation],
    prior_state: CaseStateVersion | None,
    requirements: CaseRequirements,
    eval_at: datetime,
) -> CaseStateVersion: ...

# src/advocate/processing/state_machine.py
def evaluate_stage(state: DerivedComponents, rules: list[StageRule]) -> str: ...
def compute_completion_ratio(components: dict[str, ComponentStatus], weights: dict[str, float]) -> float: ...
```

Acceptance criteria:

- one evidence item can produce observations and a new case state
- missing and stale components match the YAML config
- contradictions are visible in state output
- stage labels are derived purely from state, not side effects
- the created case state version is linked to its exact observations and configs via the evaluation manifest

TDD slice:

- unit tests for each state-machine operator
- unit tests for contradiction detection over normalized observation fields
- integration tests for observation insert to state-version materialization
- one provenance test proving the manifest captures the config and observation inputs used for a version

### Phase 5: OCR, Normalization, And Bounded LLM Extraction

Deliverables:

- OCR task for image and scanned PDFs
- text normalization pipeline for emails, transcripts, and structured notes
- schema-validated LLM extraction task
- artifact recording for prompts, models, and extraction outputs
- evaluation producer records for OCR and LLM-backed tasks
- update the phase log in docs/architecture_diagram.md

Acceptance criteria:

- scanned files create `ocr_text` artifacts
- free text creates normalized extraction artifacts
- invalid LLM responses fail safely and do not mutate state
- extraction output can be replayed into the merge engine
- model name, model version, and prompt version are auditable for LLM-backed outputs

TDD slice:

- unit tests for evidence-type routing to OCR vs normalization vs extraction
- contract tests for schema-validated LLM output
- one replay integration test from extraction artifact into merge
- one provenance test proving OCR and LLM producers are attached to the evaluation run

### Phase 6: Scoring, Hybrid Retrieval, And Next Best Action

Deliverables:

- rule-based scoring engine
- retrieval chunking and embedding pipeline
- sparse plus structured retrieval layer
- deterministic action candidate generation
- optional LLM action ranking and draft generation
- versioned scoring and retrieval producer capture in provenance
- update the phase log in docs/architecture_diagram.md

Acceptance criteria:

- a case gets `case_strength_score`, `readiness_score`, `engagement_score`, and `risk_score`
- retrieval returns ranked, evidence-linked bundles
- at least one rule-generated action appears for incomplete or stale cases
- LLM ranking never removes mandatory actions
- each prediction and action is traceable to the evaluation run that emitted it

TDD slice:

- unit tests for scoring formulas and weight handling
- unit tests for action-rule matching and ordering
- integration tests for retrieval bundle materialization
- one provenance test proving predictions and actions are attached as evaluation outputs

### Phase 7: Packet Rendering

Deliverables:

- packet templates for `application_packet`, `interview_brief`, and `follow_up_packet`
- citation assembly from evidence ids and artifact refs
- markdown and PDF rendering
- evaluation output binding for packet artifacts
- update the phase log in docs/architecture_diagram.md

Acceptance criteria:

- packets render from `CaseStateVersion`, not ad hoc prompts
- every non-trivial claim includes source evidence references
- packet artifacts are stored and versioned
- every rendered packet is attached to the case version that produced it

TDD slice:

- unit tests for packet section assembly from state inputs
- integration tests for citation rendering and artifact persistence
- one regression test per packet template
- one provenance test proving rendered packets are attached to evaluation outputs

### Phase 8: UI

Deliverables:

- guided case intake
- evidence upload UI
- case timeline
- state panel
- next best action panel
- packet review and export view
- update the phase log in docs/architecture_diagram.md

Acceptance criteria:

- can create a case and upload evidence end to end
- latest state and scores are visible without reading raw tables
- packet artifacts can be reviewed and exported

TDD slice:

- component tests for intake, timeline, and state panels
- API integration tests for the UI data contracts it consumes
- one focused end-to-end UI test for create case to upload evidence to view state

### Phase 9: Evaluation Harness

Deliverables:

- external scenario repo contract
- scenario runner
- assertions for component state, score bounds, actions, and packets
- CI target for scenario replay
- initial scenario suite defined by [specs/scenario_vision.md](/Users/dacks/repos/advocate/specs/scenario_vision.md)
- update the phase log in docs/architecture_diagram.md

Acceptance criteria:

- a scenario can replay evidence into a fresh local environment
- regressions fail with specific diffs
- scenario data is not accessible to prompts or retrieval corpora

TDD slice:

- one scenario contract parser test
- one runner integration test against a minimal scenario
- one full scenario per category from [specs/scenario_vision.md](/Users/dacks/repos/advocate/specs/scenario_vision.md) before expanding breadth

## 6. Build Order Inside The Codebase

Implement in this order:

1. `src/advocate/domain`
2. `src/advocate/storage`
3. `apps/api`
4. `src/advocate/processing`
5. `src/advocate/scoring`
6. `src/advocate/retrieval`
7. `src/advocate/rendering`
8. `src/advocate/evaluation`
9. `apps/ui`

## 7. Testing Strategy

### Unit Tests

Cover:

- component merge rules
- staleness logic
- contradiction detection
- stage derivation
- scoring calculations
- action generation

### Integration Tests

Cover:

- evidence ingestion to object storage
- flow execution for a single evidence item
- repeated processing idempotency
- packet rendering with citations

### Scenario Tests

Cover:

- full opportunity lifecycles
- conflicting evidence
- stale follow-up windows
- recruiter response and interview progression
- rejection and offer branches

Scenario tests should follow the narrative categories in [specs/scenario_vision.md](/Users/dacks/repos/advocate/specs/scenario_vision.md), not an arbitrary collection of fixtures.

Measurement rule:

- benchmark comparisons must be expressed against case evaluation runs or case state versions, not loose artifacts without provenance

## 8. Known Risks To Address Early

- poor document OCR will poison downstream extraction if confidence is ignored
- case-state growth may become expensive if every version stores large embedded blobs
- retrieval quality will drift if chunking strategy is not versioned
- packet rendering will become untrustworthy if citations are optional
- action generation will feel noisy if priorities are not deterministic
- scenario suites will become fake confidence if they stop reflecting realistic evidence arrival order
- architecture diagrams will become misleading if they are not updated in the same change as file moves

## 9. Suggested First Milestone

The first milestone should stop after Phase 4.

That gives you:

- a real case model
- file and note ingestion
- append-only evidence
- deterministic state versions
- visible missing and stale components

Required tests before leaving this milestone:

- operator-level unit tests
- append-only storage integration tests
- at least one scenario covering incomplete intake and one covering stale follow-up

Required diagram work before leaving this milestone:

- [docs/architecture_diagram.md](/Users/dacks/repos/advocate/docs/architecture_diagram.md) reflects the actual Phase 0 through Phase 4 file set and marks built files accurately

That is enough to start using the product on your real job search before adding LLMs.

## 10. Suggested Second Milestone

The second milestone should cover Phases 5 through 7.

That gives you:

- OCR and extraction
- scoring
- hybrid retrieval
- next best actions
- packet generation

Required tests before leaving this milestone:

- extraction contract tests
- retrieval bundle integration tests
- at least one contradiction scenario and one offer or rejection scenario

Required diagram work before leaving this milestone:

- [docs/architecture_diagram.md](/Users/dacks/repos/advocate/docs/architecture_diagram.md) reflects the actual Phase 5 through Phase 7 file set and any renamed files are called out

At that point, the system starts to feel like an actual advocacy-style decision-support product.
