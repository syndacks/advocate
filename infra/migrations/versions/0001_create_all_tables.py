"""Create all core tables.

Revision ID: 0001
Revises:
Create Date: 2026-03-01

Hand-written migration for all 15 tables from schema.md §9.
Order follows the dependency chain: no FK references a table created later.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension (needed for retrieval_chunks.embedding)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── 1. candidates ─────────────────────────────────────────────────────────
    op.create_table(
        "candidates",
        sa.Column("candidate_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("primary_email", sa.Text(), nullable=False),
        sa.Column("location_json", JSONB(), nullable=True),
        sa.Column("target_comp_min", sa.Integer(), nullable=True),
        sa.Column("target_comp_max", sa.Integer(), nullable=True),
        sa.Column("preferences_json", JSONB(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # ── 2. cases ──────────────────────────────────────────────────────────────
    op.create_table(
        "cases",
        sa.Column("case_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("candidate_id", UUID(as_uuid=True), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("role_title", sa.Text(), nullable=False),
        sa.Column("job_posting_url", sa.Text(), nullable=True),
        sa.Column("job_posting_id", sa.Text(), nullable=True),
        sa.Column("source_channel", sa.Text(), nullable=False),
        sa.Column("opened_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("closed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.candidate_id"], name="fk_cases_candidate_id"),
    )

    # ── 3. evidence_items ─────────────────────────────────────────────────────
    op.create_table(
        "evidence_items",
        sa.Column("evidence_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source_channel", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("evidence_type", sa.Text(), nullable=False),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("raw_blob_uri", sa.Text(), nullable=False),
        sa.Column("submitted_by", sa.Text(), nullable=False),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_evidence_items_case_id"),
    )
    op.create_index("ix_evidence_items_case_id", "evidence_items", ["case_id"])
    op.create_index("ix_evidence_items_received_at", "evidence_items", ["case_id", "received_at"])

    # ── 4. artifacts ──────────────────────────────────────────────────────────
    op.create_table(
        "artifacts",
        sa.Column("artifact_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_id", UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", UUID(as_uuid=True), nullable=True),
        sa.Column("artifact_type", sa.Text(), nullable=False),
        sa.Column("producer", sa.Text(), nullable=False),
        sa.Column("producer_version", sa.Text(), nullable=False),
        sa.Column("input_hashes_json", JSONB(), nullable=False),
        sa.Column("blob_uri", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_artifacts_case_id"),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence_items.evidence_id"], name="fk_artifacts_evidence_id"),
    )
    op.create_index("ix_artifacts_case_id", "artifacts", ["case_id"])

    # ── 5. component_observations ─────────────────────────────────────────────
    op.create_table(
        "component_observations",
        sa.Column("observation_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_id", UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", UUID(as_uuid=True), nullable=False),
        sa.Column("component_key", sa.Text(), nullable=False),
        sa.Column("value_json", JSONB(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("extractor_version", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_component_observations_case_id"),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence_items.evidence_id"], name="fk_component_observations_evidence_id"),
    )
    op.create_index("ix_component_observations_case_id", "component_observations", ["case_id"])
    op.create_index("ix_component_observations_evidence_id", "component_observations", ["evidence_id"])

    # ── 6. case_state_versions ────────────────────────────────────────────────
    op.create_table(
        "case_state_versions",
        sa.Column("case_state_version_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_id", UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("parent_version_number", sa.Integer(), nullable=True),
        sa.Column("trigger_evidence_id", UUID(as_uuid=True), nullable=False),
        sa.Column("derived_components_json", JSONB(), nullable=False),
        sa.Column("completion_metrics_json", JSONB(), nullable=False),
        sa.Column("stage_label", sa.Text(), nullable=False),
        sa.Column("risk_flags_json", JSONB(), nullable=True),
        sa.Column("prediction_outputs_json", JSONB(), nullable=True),
        sa.Column("recommended_actions_json", JSONB(), nullable=True),
        sa.Column("render_refs_json", JSONB(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_case_state_versions_case_id"),
        sa.ForeignKeyConstraint(["trigger_evidence_id"], ["evidence_items.evidence_id"], name="fk_case_state_versions_trigger_evidence_id"),
        sa.UniqueConstraint("case_id", "version_number", name="uq_case_state_versions_case_version"),
    )
    op.create_index("ix_case_state_versions_case_id", "case_state_versions", ["case_id"])

    # ── 7. case_evaluation_runs ───────────────────────────────────────────────
    op.create_table(
        "case_evaluation_runs",
        sa.Column("case_evaluation_run_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_id", UUID(as_uuid=True), nullable=False),
        sa.Column("case_state_version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("parent_case_state_version_id", UUID(as_uuid=True), nullable=True),
        sa.Column("trigger_evidence_id", UUID(as_uuid=True), nullable=False),
        sa.Column("flow_run_id", sa.Text(), nullable=True),
        sa.Column("app_version", sa.Text(), nullable=False),
        sa.Column("requirements_version", sa.Text(), nullable=False),
        sa.Column("state_machine_version", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_case_evaluation_runs_case_id"),
        sa.ForeignKeyConstraint(["case_state_version_id"], ["case_state_versions.case_state_version_id"], name="fk_case_evaluation_runs_version_id"),
        sa.ForeignKeyConstraint(["parent_case_state_version_id"], ["case_state_versions.case_state_version_id"], name="fk_case_evaluation_runs_parent_version_id"),
        sa.ForeignKeyConstraint(["trigger_evidence_id"], ["evidence_items.evidence_id"], name="fk_case_evaluation_runs_trigger_evidence_id"),
        sa.UniqueConstraint("case_state_version_id", name="uq_case_evaluation_runs_version_id"),
    )
    op.create_index("ix_case_evaluation_runs_case_id", "case_evaluation_runs", ["case_id"])

    # ── 8. evaluation_run_inputs ──────────────────────────────────────────────
    op.create_table(
        "evaluation_run_inputs",
        sa.Column("evaluation_run_input_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_evaluation_run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("input_type", sa.Text(), nullable=False),
        sa.Column("input_ref_id", UUID(as_uuid=True), nullable=True),
        sa.Column("input_hash", sa.Text(), nullable=False),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["case_evaluation_run_id"], ["case_evaluation_runs.case_evaluation_run_id"], name="fk_evaluation_run_inputs_run_id"),
    )
    op.create_index("ix_evaluation_run_inputs_run_id", "evaluation_run_inputs", ["case_evaluation_run_id"])

    # ── 9. evaluation_run_producers ───────────────────────────────────────────
    op.create_table(
        "evaluation_run_producers",
        sa.Column("evaluation_run_producer_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_evaluation_run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("producer_type", sa.Text(), nullable=False),
        sa.Column("producer_name", sa.Text(), nullable=False),
        sa.Column("producer_version", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=True),
        sa.Column("model_version", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("config_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["case_evaluation_run_id"], ["case_evaluation_runs.case_evaluation_run_id"], name="fk_evaluation_run_producers_run_id"),
    )
    op.create_index("ix_evaluation_run_producers_run_id", "evaluation_run_producers", ["case_evaluation_run_id"])

    # ── 10. prediction_runs ───────────────────────────────────────────────────
    op.create_table(
        "prediction_runs",
        sa.Column("prediction_run_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_id", UUID(as_uuid=True), nullable=False),
        sa.Column("case_state_version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("scoring_version", sa.Text(), nullable=False),
        sa.Column("feature_vector_json", JSONB(), nullable=False),
        sa.Column("outputs_json", JSONB(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_prediction_runs_case_id"),
        sa.ForeignKeyConstraint(["case_state_version_id"], ["case_state_versions.case_state_version_id"], name="fk_prediction_runs_version_id"),
    )
    op.create_index("ix_prediction_runs_case_id", "prediction_runs", ["case_id"])

    # ── 11. recommended_actions ───────────────────────────────────────────────
    op.create_table(
        "recommended_actions",
        sa.Column("recommended_action_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_id", UUID(as_uuid=True), nullable=False),
        sa.Column("case_state_version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("rationale_json", JSONB(), nullable=True),
        sa.Column("draft_artifact_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_recommended_actions_case_id"),
        sa.ForeignKeyConstraint(["case_state_version_id"], ["case_state_versions.case_state_version_id"], name="fk_recommended_actions_version_id"),
        sa.ForeignKeyConstraint(["draft_artifact_id"], ["artifacts.artifact_id"], name="fk_recommended_actions_draft_artifact_id"),
    )
    op.create_index("ix_recommended_actions_case_id", "recommended_actions", ["case_id"])

    # ── 12. processing_runs ───────────────────────────────────────────────────
    op.create_table(
        "processing_runs",
        sa.Column("processing_run_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_id", UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", UUID(as_uuid=True), nullable=False),
        sa.Column("flow_run_id", sa.Text(), nullable=True),
        sa.Column("task_name", sa.Text(), nullable=True),
        sa.Column("task_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("error_json", JSONB(), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_processing_runs_case_id"),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence_items.evidence_id"], name="fk_processing_runs_evidence_id"),
    )
    op.create_index("ix_processing_runs_case_id", "processing_runs", ["case_id"])
    op.create_index("ix_processing_runs_evidence_id", "processing_runs", ["evidence_id"])

    # ── 13. evaluation_run_outputs ────────────────────────────────────────────
    op.create_table(
        "evaluation_run_outputs",
        sa.Column("evaluation_run_output_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_evaluation_run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("output_type", sa.Text(), nullable=False),
        sa.Column("output_ref_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["case_evaluation_run_id"], ["case_evaluation_runs.case_evaluation_run_id"], name="fk_evaluation_run_outputs_run_id"),
    )
    op.create_index("ix_evaluation_run_outputs_run_id", "evaluation_run_outputs", ["case_evaluation_run_id"])

    # ── 14. audit_events ──────────────────────────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column("audit_event_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_id", UUID(as_uuid=True), nullable=True),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload_json", JSONB(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_audit_events_case_id"),
    )
    op.create_index("ix_audit_events_case_id", "audit_events", ["case_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])

    # ── 15. retrieval_chunks ──────────────────────────────────────────────────
    # Uses the vector type from pgvector (enabled above).
    op.execute("""
        CREATE TABLE retrieval_chunks (
            chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            case_id UUID REFERENCES cases(case_id),
            artifact_id UUID NOT NULL REFERENCES artifacts(artifact_id),
            chunk_type TEXT NOT NULL,
            text TEXT NOT NULL,
            metadata_json JSONB,
            embedding VECTOR(1536),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX ix_retrieval_chunks_case_id ON retrieval_chunks (case_id)")
    op.execute("CREATE INDEX ix_retrieval_chunks_artifact_id ON retrieval_chunks (artifact_id)")
    # IVFFlat index for approximate nearest-neighbour search (created after data load in production)
    # op.execute("CREATE INDEX ix_retrieval_chunks_embedding ON retrieval_chunks USING ivfflat (embedding vector_cosine_ops)")


def downgrade() -> None:
    op.drop_table("retrieval_chunks")
    op.drop_table("audit_events")
    op.drop_table("evaluation_run_outputs")
    op.drop_table("processing_runs")
    op.drop_table("recommended_actions")
    op.drop_table("prediction_runs")
    op.drop_table("evaluation_run_producers")
    op.drop_table("evaluation_run_inputs")
    op.drop_table("case_evaluation_runs")
    op.drop_table("case_state_versions")
    op.drop_table("component_observations")
    op.drop_table("artifacts")
    op.drop_table("evidence_items")
    op.drop_table("cases")
    op.drop_table("candidates")
    op.execute("DROP EXTENSION IF EXISTS vector")
