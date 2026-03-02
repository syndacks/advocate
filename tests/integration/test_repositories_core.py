"""Integration tests for Phase 1 repositories."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from advocate.domain.models import (
    ArtifactCreate,
    CandidateCreate,
    CaseCreate,
    CaseEvaluationRunCreate,
    CaseStateBundleCreate,
    CaseStateVersionCreate,
    EvaluationInputType,
    EvaluationOutputType,
    EvaluationProducerType,
    EvaluationRunInputCreate,
    EvaluationRunOutputCreate,
    EvaluationRunProducerCreate,
    EvidenceItemCreate,
)
from advocate.storage.repositories import (
    get_evaluation_bundle_for_version,
    get_latest_case_state,
    insert_artifact,
    insert_candidate,
    insert_case,
    insert_case_state_bundle,
    insert_evidence,
    list_case_evidence,
)


async def _create_candidate_and_case(session: AsyncSession) -> tuple[UUID, UUID]:
    candidate = await insert_candidate(
        session,
        CandidateCreate(
            full_name="Alex Rivera",
            primary_email=f"alex+{uuid4()}@example.com",
            target_comp_min=140000,
            target_comp_max=180000,
        ),
    )
    case = await insert_case(
        session,
        CaseCreate(
            candidate_id=candidate.candidate_id,
            company_name=f"ExampleCo-{uuid4()}",
            role_title="Senior Product Manager",
            source_channel="manual",
            metadata_json={"origin": "test"},
        ),
    )
    return candidate.candidate_id, case.case_id


@pytest.mark.integration
async def test_insert_candidate_and_case(async_db_session: AsyncSession) -> None:
    candidate_id, case_id = await _create_candidate_and_case(async_db_session)

    assert candidate_id is not None
    assert case_id is not None


@pytest.mark.integration
async def test_evidence_and_artifact_inserts_allow_duplicate_content_hash(
    async_db_session: AsyncSession,
) -> None:
    _, case_id = await _create_candidate_and_case(async_db_session)
    received_at = datetime.now(UTC)

    first_evidence = await insert_evidence(
        async_db_session,
        EvidenceItemCreate(
            case_id=case_id,
            source_channel="manual_ui",
            mime_type="text/plain",
            evidence_type="note_text",
            received_at=received_at,
            content_hash="shared-hash",
            raw_blob_uri="s3://advocate-evidence/first.txt",
            submitted_by="alex",
        ),
    )
    second_evidence = await insert_evidence(
        async_db_session,
        EvidenceItemCreate(
            case_id=case_id,
            source_channel="manual_ui",
            mime_type="text/plain",
            evidence_type="note_text",
            received_at=received_at + timedelta(minutes=1),
            content_hash="shared-hash",
            raw_blob_uri="s3://advocate-evidence/second.txt",
            submitted_by="alex",
        ),
    )

    artifact = await insert_artifact(
        async_db_session,
        ArtifactCreate(
            case_id=case_id,
            evidence_id=first_evidence.evidence_id,
            artifact_type="normalized_text",
            producer="normalize_evidence",
            producer_version="1.0.0",
            input_hashes_json=["shared-hash"],
            blob_uri="s3://advocate-artifacts/normalized.txt",
            content_hash="artifact-hash",
            metadata_json={"pages": 1},
        ),
    )

    timeline = await list_case_evidence(async_db_session, case_id)

    assert first_evidence.evidence_id != second_evidence.evidence_id
    assert artifact.artifact_id is not None
    assert [item.evidence_id for item in timeline] == [
        first_evidence.evidence_id,
        second_evidence.evidence_id,
    ]


@pytest.mark.integration
async def test_insert_case_state_bundle_and_read_latest_state(
    async_db_session: AsyncSession,
) -> None:
    _, case_id = await _create_candidate_and_case(async_db_session)
    evidence = await insert_evidence(
        async_db_session,
        EvidenceItemCreate(
            case_id=case_id,
            source_channel="browser_clip",
            mime_type="text/plain",
            evidence_type="web_job_posting",
            received_at=datetime.now(UTC),
            content_hash=f"job-{uuid4()}",
            raw_blob_uri="s3://advocate-evidence/job.txt",
            submitted_by="alex",
        ),
    )

    bundle = await insert_case_state_bundle(
        async_db_session,
        CaseStateBundleCreate(
            state_version=CaseStateVersionCreate(
                case_id=case_id,
                version_number=1,
                trigger_evidence_id=evidence.evidence_id,
                derived_components_json={"opportunity": {"target_role": True}},
                completion_metrics_json={"completion_ratio": 0.25},
                stage_label="intake",
            ),
            evaluation_run=CaseEvaluationRunCreate(
                case_id=case_id,
                trigger_evidence_id=evidence.evidence_id,
                app_version="0.1.0",
                requirements_version="2026-03-02",
                state_machine_version="2026-03-02",
            ),
            evaluation_inputs=[
                EvaluationRunInputCreate(
                    input_type=EvaluationInputType.EVIDENCE,
                    input_ref_id=evidence.evidence_id,
                    input_hash=evidence.content_hash,
                    metadata_json={"source": "job_posting"},
                )
            ],
            evaluation_producers=[
                EvaluationRunProducerCreate(
                    producer_type=EvaluationProducerType.MERGE,
                    producer_name="merge_case_state",
                    producer_version="1.0.0",
                    config_hash="cfg-1",
                )
            ],
            evaluation_outputs=[
                EvaluationRunOutputCreate(
                    output_type=EvaluationOutputType.CASE_STATE,
                    output_ref_id=uuid4(),
                )
            ],
        ),
    )

    latest_state = await get_latest_case_state(async_db_session, case_id)
    stored_bundle = await get_evaluation_bundle_for_version(
        async_db_session, bundle.state_version.case_state_version_id
    )

    assert latest_state is not None
    assert latest_state.case_state_version_id == bundle.state_version.case_state_version_id
    assert stored_bundle is not None
    assert stored_bundle.evaluation_run.case_state_version_id == latest_state.case_state_version_id
    assert len(stored_bundle.evaluation_inputs) == 1
    assert len(stored_bundle.evaluation_producers) == 1
    assert len(stored_bundle.evaluation_outputs) == 1
