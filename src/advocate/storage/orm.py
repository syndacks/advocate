"""SQLAlchemy ORM mappings for the Phase 1 core data layer."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CandidateORM(Base):
    __tablename__ = "candidates"

    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    primary_email: Mapped[str] = mapped_column(Text, nullable=False)
    location_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    target_comp_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_comp_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preferences_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CaseORM(Base):
    __tablename__ = "cases"

    case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    candidate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("candidates.candidate_id"), nullable=False
    )
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    role_title: Mapped[str] = mapped_column(Text, nullable=False)
    job_posting_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_posting_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_channel: Mapped[str] = mapped_column(Text, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class EvidenceItemORM(Base):
    __tablename__ = "evidence_items"

    evidence_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("cases.case_id"), nullable=False, index=True
    )
    source_channel: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_type: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    raw_blob_uri: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_by: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ArtifactORM(Base):
    __tablename__ = "artifacts"

    artifact_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("cases.case_id"), nullable=False, index=True
    )
    evidence_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("evidence_items.evidence_id"), nullable=True
    )
    artifact_type: Mapped[str] = mapped_column(Text, nullable=False)
    producer: Mapped[str] = mapped_column(Text, nullable=False)
    producer_version: Mapped[str] = mapped_column(Text, nullable=False)
    input_hashes_json: Mapped[Any] = mapped_column(JSONB, nullable=False)
    blob_uri: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ComponentObservationORM(Base):
    __tablename__ = "component_observations"

    observation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("cases.case_id"), nullable=False, index=True
    )
    evidence_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("evidence_items.evidence_id"), nullable=False, index=True
    )
    component_key: Mapped[str] = mapped_column(Text, nullable=False)
    value_json: Mapped[Any] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    extractor_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CaseStateVersionORM(Base):
    __tablename__ = "case_state_versions"
    __table_args__ = (
        UniqueConstraint("case_id", "version_number", name="uq_case_state_versions_case_version"),
    )

    case_state_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("cases.case_id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trigger_evidence_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("evidence_items.evidence_id"), nullable=False
    )
    derived_components_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    completion_metrics_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    stage_label: Mapped[str] = mapped_column(Text, nullable=False)
    risk_flags_json: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    prediction_outputs_json: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    recommended_actions_json: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    render_refs_json: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CaseEvaluationRunORM(Base):
    __tablename__ = "case_evaluation_runs"

    case_evaluation_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("cases.case_id"), nullable=False, index=True
    )
    case_state_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("case_state_versions.case_state_version_id"),
        nullable=False,
        unique=True,
    )
    parent_case_state_version_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("case_state_versions.case_state_version_id"), nullable=True
    )
    trigger_evidence_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("evidence_items.evidence_id"), nullable=False
    )
    flow_run_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    app_version: Mapped[str] = mapped_column(Text, nullable=False)
    requirements_version: Mapped[str] = mapped_column(Text, nullable=False)
    state_machine_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvaluationRunInputORM(Base):
    __tablename__ = "evaluation_run_inputs"

    evaluation_run_input_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    case_evaluation_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("case_evaluation_runs.case_evaluation_run_id"),
        nullable=False,
        index=True,
    )
    input_type: Mapped[str] = mapped_column(Text, nullable=False)
    input_ref_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    input_hash: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvaluationRunProducerORM(Base):
    __tablename__ = "evaluation_run_producers"

    evaluation_run_producer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    case_evaluation_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("case_evaluation_runs.case_evaluation_run_id"),
        nullable=False,
        index=True,
    )
    producer_type: Mapped[str] = mapped_column(Text, nullable=False)
    producer_name: Mapped[str] = mapped_column(Text, nullable=False)
    producer_version: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EvaluationRunOutputORM(Base):
    __tablename__ = "evaluation_run_outputs"

    evaluation_run_output_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    case_evaluation_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("case_evaluation_runs.case_evaluation_run_id"),
        nullable=False,
        index=True,
    )
    output_type: Mapped[str] = mapped_column(Text, nullable=False)
    output_ref_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditEventORM(Base):
    __tablename__ = "audit_events"

    audit_event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    case_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("cases.case_id"), nullable=True, index=True
    )
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
