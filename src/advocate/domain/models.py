"""Pydantic domain models for the core data layer."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

JsonValue = dict[str, Any] | list[Any]


class EvidenceSourceChannel(str, Enum):
    MANUAL_UI = "manual_ui"
    EMAIL_FORWARD = "email_forward"
    BROWSER_CLIP = "browser_clip"
    CALENDAR_IMPORT = "calendar_import"
    API = "api"
    BULK_IMPORT = "bulk_import"
    SYSTEM_GENERATED = "system_generated"


class EvidenceType(str, Enum):
    DOCUMENT_PDF = "document_pdf"
    DOCUMENT_IMAGE = "document_image"
    MESSAGE_EMAIL = "message_email"
    NOTE_TEXT = "note_text"
    TRANSCRIPT_TEXT = "transcript_text"
    STRUCTURED_JSON = "structured_json"
    CALENDAR_EVENT = "calendar_event"
    WEB_JOB_POSTING = "web_job_posting"


class ActorType(str, Enum):
    SYSTEM = "system"
    USER = "user"
    WORKER = "worker"


class EvaluationInputType(str, Enum):
    EVIDENCE = "evidence"
    ARTIFACT = "artifact"
    OBSERVATION = "observation"
    CONFIG = "config"


class EvaluationProducerType(str, Enum):
    OCR = "ocr"
    EXTRACTOR = "extractor"
    SCORER = "scorer"
    RENDERER = "renderer"
    RETRIEVER = "retriever"
    MERGE = "merge"


class EvaluationOutputType(str, Enum):
    CASE_STATE = "case_state"
    PREDICTION = "prediction"
    ACTION = "action"
    ARTIFACT = "artifact"


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class CandidateBase(DomainModel):
    full_name: str
    primary_email: str
    location_json: dict[str, Any] | None = None
    target_comp_min: int | None = None
    target_comp_max: int | None = None
    preferences_json: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_comp_range(self) -> "CandidateBase":
        if (
            self.target_comp_min is not None
            and self.target_comp_max is not None
            and self.target_comp_min > self.target_comp_max
        ):
            raise ValueError("target_comp_min must be less than or equal to target_comp_max")
        return self


class CandidateCreate(CandidateBase):
    pass


class CandidateRecord(CandidateBase):
    candidate_id: UUID
    created_at: datetime
    updated_at: datetime


class CaseBase(DomainModel):
    candidate_id: UUID
    company_name: str
    role_title: str
    job_posting_url: str | None = None
    job_posting_id: str | None = None
    source_channel: str
    status: str = "open"
    metadata_json: dict[str, Any] | None = None
    opened_at: datetime | None = None
    closed_at: datetime | None = None


class CaseCreate(CaseBase):
    pass


class CaseRecord(CaseBase):
    case_id: UUID


class EvidenceItemBase(DomainModel):
    case_id: UUID
    source_channel: EvidenceSourceChannel
    source_ref: str | None = None
    mime_type: str
    evidence_type: EvidenceType
    received_at: datetime
    content_hash: str
    raw_blob_uri: str
    submitted_by: str
    metadata_json: dict[str, Any] | None = None


class EvidenceItemCreate(EvidenceItemBase):
    pass


class EvidenceItemRecord(EvidenceItemBase):
    evidence_id: UUID
    created_at: datetime


class ArtifactBase(DomainModel):
    case_id: UUID
    evidence_id: UUID | None = None
    artifact_type: str
    producer: str
    producer_version: str
    input_hashes_json: JsonValue
    blob_uri: str
    content_hash: str
    metadata_json: dict[str, Any] | None = None


class ArtifactCreate(ArtifactBase):
    pass


class ArtifactRecord(ArtifactBase):
    artifact_id: UUID
    created_at: datetime


class ComponentObservationBase(DomainModel):
    case_id: UUID
    evidence_id: UUID
    component_key: str
    value_json: JsonValue
    confidence: float
    source_type: str
    extractor_version: str

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return value


class ComponentObservationCreate(ComponentObservationBase):
    pass


class ComponentObservationRecord(ComponentObservationBase):
    observation_id: UUID
    created_at: datetime


class CaseStateVersionBase(DomainModel):
    case_id: UUID
    version_number: int
    parent_version_number: int | None = None
    trigger_evidence_id: UUID
    derived_components_json: dict[str, Any]
    completion_metrics_json: dict[str, Any]
    stage_label: str
    risk_flags_json: JsonValue | None = None
    prediction_outputs_json: JsonValue | None = None
    recommended_actions_json: JsonValue | None = None
    render_refs_json: JsonValue | None = None

    @model_validator(mode="after")
    def validate_version_numbers(self) -> "CaseStateVersionBase":
        if self.parent_version_number is not None and self.parent_version_number >= self.version_number:
            raise ValueError("parent_version_number must be less than version_number")
        return self


class CaseStateVersionCreate(CaseStateVersionBase):
    pass


class CaseStateVersionRecord(CaseStateVersionBase):
    case_state_version_id: UUID
    created_at: datetime


class CaseEvaluationRunBase(DomainModel):
    case_id: UUID
    parent_case_state_version_id: UUID | None = None
    trigger_evidence_id: UUID
    flow_run_id: str | None = None
    app_version: str
    requirements_version: str
    state_machine_version: str


class CaseEvaluationRunCreate(CaseEvaluationRunBase):
    pass


class CaseEvaluationRunRecord(CaseEvaluationRunBase):
    case_evaluation_run_id: UUID
    case_state_version_id: UUID
    created_at: datetime


class EvaluationRunInputBase(DomainModel):
    input_type: EvaluationInputType
    input_ref_id: UUID | None = None
    input_hash: str
    metadata_json: dict[str, Any] | None = None


class EvaluationRunInputCreate(EvaluationRunInputBase):
    pass


class EvaluationRunInputRecord(EvaluationRunInputBase):
    evaluation_run_input_id: UUID
    case_evaluation_run_id: UUID
    created_at: datetime


class EvaluationRunProducerBase(DomainModel):
    producer_type: EvaluationProducerType
    producer_name: str
    producer_version: str
    model_name: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    config_hash: str


class EvaluationRunProducerCreate(EvaluationRunProducerBase):
    pass


class EvaluationRunProducerRecord(EvaluationRunProducerBase):
    evaluation_run_producer_id: UUID
    case_evaluation_run_id: UUID
    created_at: datetime


class EvaluationRunOutputBase(DomainModel):
    output_type: EvaluationOutputType
    output_ref_id: UUID


class EvaluationRunOutputCreate(EvaluationRunOutputBase):
    pass


class EvaluationRunOutputRecord(EvaluationRunOutputBase):
    evaluation_run_output_id: UUID
    case_evaluation_run_id: UUID
    created_at: datetime


class AuditEventBase(DomainModel):
    case_id: UUID | None = None
    actor_type: ActorType = ActorType.SYSTEM
    actor_id: str = "advocate"
    event_type: str
    payload_json: dict[str, Any] | None = None


class AuditEventCreate(AuditEventBase):
    pass


class AuditEventRecord(AuditEventBase):
    audit_event_id: UUID
    created_at: datetime


class CaseStateBundleCreate(DomainModel):
    state_version: CaseStateVersionCreate
    evaluation_run: CaseEvaluationRunCreate
    evaluation_inputs: list[EvaluationRunInputCreate] = Field(default_factory=list)
    evaluation_producers: list[EvaluationRunProducerCreate] = Field(default_factory=list)
    evaluation_outputs: list[EvaluationRunOutputCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_alignment(self) -> "CaseStateBundleCreate":
        if self.state_version.case_id != self.evaluation_run.case_id:
            raise ValueError("state_version.case_id must match evaluation_run.case_id")
        if self.state_version.trigger_evidence_id != self.evaluation_run.trigger_evidence_id:
            raise ValueError(
                "state_version.trigger_evidence_id must match evaluation_run.trigger_evidence_id"
            )
        return self


class CaseStateBundleRecord(DomainModel):
    state_version: CaseStateVersionRecord
    evaluation_run: CaseEvaluationRunRecord
    evaluation_inputs: list[EvaluationRunInputRecord] = Field(default_factory=list)
    evaluation_producers: list[EvaluationRunProducerRecord] = Field(default_factory=list)
    evaluation_outputs: list[EvaluationRunOutputRecord] = Field(default_factory=list)
