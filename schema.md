# Concrete Schema And Folder Layout

## 1. Scope

This document turns [architecture.md](/Users/dacks/repos/advocate/architecture.md) into concrete storage, event, and repository contracts for the first build.

The system remains centered on three invariants:

- evidence is append-only
- all user-facing conclusions come from `case_state_versions`
- flows are stateless and replayable

Versioning and auditability follow one additional invariant:

- every `CaseStateVersion` must be traceable to exactly one evaluation manifest

## 2. Storage Stack

Use this baseline stack for the first implementation:

- Postgres for relational truth
- pgvector for embeddings
- S3-compatible object storage for raw evidence and derived artifacts
- Redis only for ephemeral locks and short-lived cache entries
- Prefect for orchestration metadata and flow execution

Canonical taxonomy and contracts live here:

- [specs/evidence_taxonomy.md](/Users/dacks/repos/advocate/specs/evidence_taxonomy.md)
- [specs/observations.md](/Users/dacks/repos/advocate/specs/observations.md)
- [specs/state_machine.md](/Users/dacks/repos/advocate/specs/state_machine.md)
- [specs/scenario_vision.md](/Users/dacks/repos/advocate/specs/scenario_vision.md)

## 3. Canonical Entities

### 3.1 `candidates`

Represents the underlying job seeker.

| Column | Type | Notes |
| --- | --- | --- |
| `candidate_id` | UUID PK | Stable identifier |
| `full_name` | TEXT | |
| `primary_email` | TEXT | |
| `location_json` | JSONB | City, state, remote preference |
| `target_comp_min` | INTEGER | Optional |
| `target_comp_max` | INTEGER | Optional |
| `preferences_json` | JSONB | Domain, company stage, work mode |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | Mutable profile metadata only |

### 3.2 `cases`

One opportunity pursuit per company and role.

| Column | Type | Notes |
| --- | --- | --- |
| `case_id` | UUID PK | |
| `candidate_id` | UUID FK | References `candidates` |
| `company_name` | TEXT | |
| `role_title` | TEXT | |
| `job_posting_url` | TEXT | Nullable |
| `job_posting_id` | TEXT | Nullable external req id |
| `source_channel` | TEXT | Manual, referral, recruiter, inbound |
| `opened_at` | TIMESTAMPTZ | |
| `closed_at` | TIMESTAMPTZ | Nullable |
| `status` | TEXT | Operational status only |
| `metadata_json` | JSONB | Immutable source metadata |

Constraint:

- `status` is not the analytical truth. It is only a case container status.

### 3.3 `evidence_items`

Immutable raw evidence records.

| Column | Type | Notes |
| --- | --- | --- |
| `evidence_id` | UUID PK | |
| `case_id` | UUID FK | |
| `source_channel` | TEXT | Canonical ingress enum from `specs/evidence_taxonomy.md` |
| `source_ref` | TEXT | Original message id, file id, etc. |
| `mime_type` | TEXT | |
| `evidence_type` | TEXT | Canonical semantic enum from `specs/evidence_taxonomy.md` |
| `received_at` | TIMESTAMPTZ | |
| `content_hash` | TEXT | SHA-256 of raw payload |
| `raw_blob_uri` | TEXT | Object storage URI |
| `submitted_by` | TEXT | User or system actor |
| `metadata_json` | JSONB | Filename, sender, subject, timestamps |
| `created_at` | TIMESTAMPTZ | Insert time |

Invariants:

- rows are never updated in place
- duplicate payloads may share the same `content_hash`
- deduplication decisions happen in processing, not by rejecting inserts

### 3.4 `artifacts`

Derived outputs from any processing task.

| Column | Type | Notes |
| --- | --- | --- |
| `artifact_id` | UUID PK | |
| `case_id` | UUID FK | |
| `evidence_id` | UUID FK | Nullable for multi-input artifacts |
| `artifact_type` | TEXT | See artifact enum below |
| `producer` | TEXT | Task or service name |
| `producer_version` | TEXT | Immutable task version |
| `input_hashes_json` | JSONB | Hashes of all inputs |
| `blob_uri` | TEXT | Object storage URI |
| `content_hash` | TEXT | Hash of rendered artifact |
| `metadata_json` | JSONB | Confidence, page count, citations |
| `created_at` | TIMESTAMPTZ | |

Suggested `artifact_type` values:

- `ocr_text`
- `normalized_text`
- `llm_extraction`
- `embedding`
- `feature_vector`
- `timeline_summary`
- `packet_markdown`
- `packet_pdf`
- `outreach_draft`
- `retrieval_bundle`

### 3.5 `component_observations`

Evidence-linked observations before state materialization.

| Column | Type | Notes |
| --- | --- | --- |
| `observation_id` | UUID PK | |
| `case_id` | UUID FK | |
| `evidence_id` | UUID FK | |
| `component_key` | TEXT | Example: `relevance.quantified_impact_examples` |
| `value_json` | JSONB | Normalized observation payload defined in `specs/observations.md` |
| `confidence` | NUMERIC(4,3) | 0.000 to 1.000 |
| `source_type` | TEXT | `rule`, `ocr`, `llm`, `human` |
| `extractor_version` | TEXT | |
| `created_at` | TIMESTAMPTZ | |

This table is append-only and allows replay of merge behavior.

### 3.6 `case_state_versions`

The authoritative analytical truth.

| Column | Type | Notes |
| --- | --- | --- |
| `case_state_version_id` | UUID PK | |
| `case_id` | UUID FK | |
| `version_number` | INTEGER | Monotonic per case |
| `parent_version_number` | INTEGER | Nullable for version 1 |
| `trigger_evidence_id` | UUID FK | Evidence that caused this recomputation |
| `derived_components_json` | JSONB | Full materialized component graph |
| `completion_metrics_json` | JSONB | Missing, stale, contradicted, readiness |
| `stage_label` | TEXT | Derived view |
| `risk_flags_json` | JSONB | Structured flags |
| `prediction_outputs_json` | JSONB | Scores and feature refs |
| `recommended_actions_json` | JSONB | Ranked actions with rationale |
| `render_refs_json` | JSONB | Pointers to latest packet artifacts |
| `created_at` | TIMESTAMPTZ | |

Constraints:

- unique `(case_id, version_number)`
- no updates after insert

`case_state_versions` is the canonical truth snapshot, but it is not the full provenance record. Provenance lives in `case_evaluation_runs` and related tables below.

### 3.7 `case_evaluation_runs`

The immutable provenance manifest for one case evaluation.

| Column | Type | Notes |
| --- | --- | --- |
| `case_evaluation_run_id` | UUID PK | |
| `case_id` | UUID FK | |
| `case_state_version_id` | UUID FK UNIQUE | Exactly one manifest per state version |
| `parent_case_state_version_id` | UUID FK | Nullable for the first version |
| `trigger_evidence_id` | UUID FK | Evidence that caused recomputation |
| `flow_run_id` | TEXT | Prefect identifier |
| `app_version` | TEXT | Git SHA, image tag, or release version |
| `requirements_version` | TEXT | Version of `case_requirements.yaml` |
| `state_machine_version` | TEXT | Version of state semantics contract |
| `created_at` | TIMESTAMPTZ | |

This table answers:

- what run created this case version
- what application build created it
- what ruleset version governed it

### 3.8 `evaluation_run_inputs`

The normalized list of inputs that were in scope for an evaluation run.

| Column | Type | Notes |
| --- | --- | --- |
| `evaluation_run_input_id` | UUID PK | |
| `case_evaluation_run_id` | UUID FK | |
| `input_type` | TEXT | `evidence`, `artifact`, `observation`, `config` |
| `input_ref_id` | UUID | Nullable for non-row-backed config refs |
| `input_hash` | TEXT | Hash or checksum of the effective input |
| `metadata_json` | JSONB | Human-legible provenance details |
| `created_at` | TIMESTAMPTZ | |

This table makes the evaluation replayable and lets you answer which evidence and derived inputs actually fed a version.

### 3.9 `evaluation_run_producers`

The producer, model, and prompt lineage used during an evaluation run.

| Column | Type | Notes |
| --- | --- | --- |
| `evaluation_run_producer_id` | UUID PK | |
| `case_evaluation_run_id` | UUID FK | |
| `producer_type` | TEXT | `ocr`, `extractor`, `scorer`, `renderer`, `retriever`, `merge` |
| `producer_name` | TEXT | Task or subsystem name |
| `producer_version` | TEXT | Immutable code or function version |
| `model_name` | TEXT | Nullable for non-LLM producers |
| `model_version` | TEXT | Nullable |
| `prompt_version` | TEXT | Nullable |
| `config_hash` | TEXT | Hash of effective config |
| `created_at` | TIMESTAMPTZ | |

This table answers which models, prompts, and function versions contributed to a case version.

### 3.10 `prediction_runs`

Append-only scoring outputs for audit.

| Column | Type | Notes |
| --- | --- | --- |
| `prediction_run_id` | UUID PK | |
| `case_id` | UUID FK | |
| `case_state_version_id` | UUID FK | |
| `scoring_version` | TEXT | |
| `feature_vector_json` | JSONB | Deterministic inputs |
| `outputs_json` | JSONB | Case strength, risk, readiness |
| `created_at` | TIMESTAMPTZ | |

### 3.11 `recommended_actions`

Normalized action candidates for timeline and audit.

| Column | Type | Notes |
| --- | --- | --- |
| `recommended_action_id` | UUID PK | |
| `case_id` | UUID FK | |
| `case_state_version_id` | UUID FK | |
| `action_type` | TEXT | Deterministic category |
| `priority` | INTEGER | Lower is higher priority |
| `title` | TEXT | |
| `rationale_json` | JSONB | Rule outputs and evidence refs |
| `draft_artifact_id` | UUID FK | Nullable |
| `status` | TEXT | `open`, `dismissed`, `completed` |
| `created_at` | TIMESTAMPTZ | |

### 3.12 `processing_runs`

Tracks orchestration of evidence processing.

| Column | Type | Notes |
| --- | --- | --- |
| `processing_run_id` | UUID PK | |
| `case_id` | UUID FK | |
| `evidence_id` | UUID FK | |
| `flow_run_id` | TEXT | Prefect identifier |
| `task_name` | TEXT | Nullable for task-level rows |
| `task_version` | TEXT | |
| `status` | TEXT | `queued`, `running`, `failed`, `completed` |
| `attempt` | INTEGER | |
| `error_json` | JSONB | Nullable |
| `started_at` | TIMESTAMPTZ | |
| `finished_at` | TIMESTAMPTZ | Nullable |

### 3.13 `evaluation_run_outputs`

The outputs materially attached to an evaluation run.

| Column | Type | Notes |
| --- | --- | --- |
| `evaluation_run_output_id` | UUID PK | |
| `case_evaluation_run_id` | UUID FK | |
| `output_type` | TEXT | `case_state`, `prediction`, `action`, `artifact` |
| `output_ref_id` | UUID | Row id of the attached output |
| `created_at` | TIMESTAMPTZ | |

Rule:

- an output may attach to a case version only if it is emitted by the evaluation run for that version

### 3.14 `audit_events`

Immutable operational audit trail.

| Column | Type | Notes |
| --- | --- | --- |
| `audit_event_id` | UUID PK | |
| `case_id` | UUID FK | Nullable |
| `actor_type` | TEXT | `system`, `user`, `worker` |
| `actor_id` | TEXT | |
| `event_type` | TEXT | |
| `payload_json` | JSONB | |
| `created_at` | TIMESTAMPTZ | |

## 4. Retrieval Indexes

Use two retrieval surfaces in parallel.

### 4.1 Dense Vector Index

Store embeddings for:

- normalized evidence text
- resume bullets
- work-history achievements
- packet snippets
- outreach examples

Suggested table:

`retrieval_chunks`

| Column | Type | Notes |
| --- | --- | --- |
| `chunk_id` | UUID PK | |
| `case_id` | UUID FK | Nullable for global corpora |
| `artifact_id` | UUID FK | Source artifact |
| `chunk_type` | TEXT | `job_requirement`, `resume_bullet`, `achievement`, `message_email`, `packet` |
| `text` | TEXT | |
| `metadata_json` | JSONB | Role, company, dates, tags |
| `embedding` | VECTOR | pgvector |
| `created_at` | TIMESTAMPTZ | |

### 4.2 Sparse And Structured Retrieval

Maintain:

- trigram or full-text indexes on `text`
- structured filters on role family, company, seniority, quantified impact, source recency

Retrieval output should be materialized as `retrieval_bundle` artifacts so downstream rendering is reproducible.

## 5. Event Contracts

### 5.1 Evidence Received Event

```json
{
  "event_type": "evidence.received",
  "case_id": "uuid",
  "evidence_id": "uuid",
  "received_at": "2026-02-28T12:00:00Z",
  "content_hash": "sha256",
  "source_channel": "manual_ui",
  "evidence_type": "document_pdf"
}
```

### 5.2 Packet Render Requested Event

```json
{
  "event_type": "packet.render_requested",
  "case_id": "uuid",
  "case_state_version_id": "uuid",
  "packet_type": "interview_brief"
}
```

## 6. API Surface

The first implementation only needs a narrow service boundary.

### 6.1 Ingestion API

- `POST /candidates`
- `POST /cases`
- `POST /cases/{case_id}/evidence`
- `POST /cases/{case_id}/notes`
- `GET /cases/{case_id}`
- `GET /cases/` (get all cases so a user can see them)
- `GET /cases/{case_id}/timeline`
- `GET /cases/{case_id}/state/latest`
- `GET /cases/{case_id}/packets`

### 6.2 Internal Worker API

- `POST /internal/process-case-event`
- `POST /internal/render-packet`
- `POST /internal/recompute-case`

## 7. Merge Contract

The merge step should consume:

- latest `case_state_versions`
- relevant `component_observations`
- requirement config from [case_requirements.yaml](/Users/dacks/repos/advocate/case_requirements.yaml)
- operator semantics from [specs/state_machine.md](/Users/dacks/repos/advocate/specs/state_machine.md)
- observation schemas from [specs/observations.md](/Users/dacks/repos/advocate/specs/observations.md)

The merge step must emit:

- a new `case_state_versions` row
- a new `case_evaluation_runs` row
- `evaluation_run_inputs` for evidence, artifacts, observations, and configs in scope
- `evaluation_run_producers` for every material subsystem that ran
- optional new `prediction_runs`
- optional new `recommended_actions`
- optional new packet artifacts
- `evaluation_run_outputs` that bind those outputs to the created case version

## 8. Recommended Folder Layout

This is the first-pass repository layout to support the architecture:

```text
advocate/
  apps/
    api/
    ui/
    worker/
  configs/
  docs/
  infra/
    migrations/
  specs/
  src/
    advocate/
      domain/
      evaluation/
      ingestion/
      processing/
      rendering/
      retrieval/
      scoring/
      storage/
  tests/
    integration/
    scenarios/
    unit/
  architecture.md
  case_requirements.yaml
  implementation_plan.md
  requirements_original.txt
  schema.md
```

Directory purpose:

- `apps/api`: HTTP endpoints, request validation, auth, ingestion adapters
- `apps/ui`: case timeline, packet review, intake, and observability views
- `apps/worker`: Prefect entrypoints and queue consumers
- `configs`: non-secret runtime config and flow settings
- `infra/migrations`: database migrations
- `specs`: executable contracts for taxonomy, observations, state semantics, and scenarios
- `src/advocate/domain`: typed models and merge logic
- `src/advocate/ingestion`: evidence ingestion and durable storage adapters
- `src/advocate/processing`: Prefect flows and task implementations
- `src/advocate/retrieval`: dense, sparse, and structured retrieval code
- `src/advocate/rendering`: packet renderers and citation assembly
- `src/advocate/scoring`: rule-based scoring and action generation
- `src/advocate/storage`: repositories and object storage clients
- `src/advocate/evaluation`: scenario runner and assertions

## 9. Suggested Initial Migration Order

1. `candidates`
2. `cases`
3. `evidence_items`
4. `artifacts`
5. `component_observations`
6. `case_state_versions`
7. `case_evaluation_runs`
8. `evaluation_run_inputs`
9. `evaluation_run_producers`
10. `prediction_runs`
11. `recommended_actions`
12. `processing_runs`
13. `evaluation_run_outputs`
14. `audit_events`
15. `retrieval_chunks`

## 10. Ground Rules

- Never read raw evidence directly from the UI to derive user-facing conclusions.
- Never update `case_state_versions` in place.
- Never let LLM output bypass schema validation and deterministic merge code.
- Never let retrieval results stand in for final truth without evidence links.
- Never attach a prediction, packet, or action to a case version unless it is traceable through that version's evaluation manifest.
