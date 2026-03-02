"""Unit tests for Phase 1 domain models."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from advocate.domain.models import (
    CandidateCreate,
    CaseEvaluationRunCreate,
    CaseStateBundleCreate,
    CaseStateVersionCreate,
    ComponentObservationCreate,
    EvidenceItemCreate,
)


def test_candidate_create_accepts_valid_comp_range() -> None:
    candidate = CandidateCreate(
        full_name="Alex Rivera",
        primary_email="alex@example.com",
        target_comp_min=140000,
        target_comp_max=180000,
    )

    assert candidate.target_comp_min == 140000
    assert candidate.target_comp_max == 180000


def test_candidate_create_rejects_invalid_comp_range() -> None:
    with pytest.raises(ValidationError):
        CandidateCreate(
            full_name="Alex Rivera",
            primary_email="alex@example.com",
            target_comp_min=180000,
            target_comp_max=140000,
        )


def test_evidence_item_rejects_invalid_source_channel() -> None:
    with pytest.raises(ValidationError):
        EvidenceItemCreate(
            case_id=uuid4(),
            source_channel="recruiter_dm",
            mime_type="text/plain",
            evidence_type="note_text",
            received_at=datetime.now(UTC),
            content_hash="abc123",
            raw_blob_uri="s3://bucket/evidence.txt",
            submitted_by="alex",
        )


def test_evidence_item_rejects_invalid_evidence_type() -> None:
    with pytest.raises(ValidationError):
        EvidenceItemCreate(
            case_id=uuid4(),
            source_channel="manual_ui",
            mime_type="text/plain",
            evidence_type="slack_message",
            received_at=datetime.now(UTC),
            content_hash="abc123",
            raw_blob_uri="s3://bucket/evidence.txt",
            submitted_by="alex",
        )


def test_component_observation_confidence_must_be_in_range() -> None:
    with pytest.raises(ValidationError):
        ComponentObservationCreate(
            case_id=uuid4(),
            evidence_id=uuid4(),
            component_key="relevance.requirement_coverage",
            value_json={"coverage_ratio": 0.5},
            confidence=1.1,
            source_type="rule",
            extractor_version="1.0.0",
        )


def test_case_state_version_requires_parent_lower_than_version() -> None:
    with pytest.raises(ValidationError):
        CaseStateVersionCreate(
            case_id=uuid4(),
            version_number=2,
            parent_version_number=2,
            trigger_evidence_id=uuid4(),
            derived_components_json={},
            completion_metrics_json={},
            stage_label="submitted",
        )


def test_case_state_bundle_requires_matching_case_and_trigger_evidence() -> None:
    case_id = uuid4()
    trigger_evidence_id = uuid4()

    with pytest.raises(ValidationError):
        CaseStateBundleCreate(
            state_version=CaseStateVersionCreate(
                case_id=case_id,
                version_number=1,
                trigger_evidence_id=trigger_evidence_id,
                derived_components_json={},
                completion_metrics_json={},
                stage_label="intake",
            ),
            evaluation_run=CaseEvaluationRunCreate(
                case_id=uuid4(),
                trigger_evidence_id=uuid4(),
                app_version="0.1.0",
                requirements_version="2026-03-02",
                state_machine_version="2026-03-02",
            ),
        )
