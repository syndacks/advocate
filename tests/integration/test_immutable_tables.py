"""Integration tests for append-only database protections."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from advocate.domain.models import (
    CandidateCreate,
    CaseCreate,
    CaseEvaluationRunCreate,
    CaseStateBundleCreate,
    CaseStateVersionCreate,
    EvidenceItemCreate,
)
from advocate.storage.audit import write_audit_event
from advocate.storage.orm import CaseEvaluationRunORM
from advocate.storage.repositories import (
    insert_candidate,
    insert_case,
    insert_case_state_bundle,
    insert_evidence,
)


async def _create_case_with_evidence(session: AsyncSession) -> tuple[UUID, UUID, UUID]:
    candidate = await insert_candidate(
        session,
        CandidateCreate(
            full_name="Alex Rivera",
            primary_email=f"alex+{uuid4()}@example.com",
        ),
    )
    case = await insert_case(
        session,
        CaseCreate(
            candidate_id=candidate.candidate_id,
            company_name=f"ExampleCo-{uuid4()}",
            role_title="Senior Product Manager",
            source_channel="manual",
        ),
    )
    evidence = await insert_evidence(
        session,
        EvidenceItemCreate(
            case_id=case.case_id,
            source_channel="manual_ui",
            mime_type="text/plain",
            evidence_type="note_text",
            received_at=datetime.now(UTC),
            content_hash=f"hash-{uuid4()}",
            raw_blob_uri="s3://advocate-evidence/evidence.txt",
            submitted_by="alex",
        ),
    )
    return candidate.candidate_id, case.case_id, evidence.evidence_id


@pytest.mark.integration
async def test_evidence_items_reject_update(async_db_session: AsyncSession) -> None:
    _, _, evidence_id = await _create_case_with_evidence(async_db_session)

    with pytest.raises(DBAPIError, match="append-only"):
        await async_db_session.execute(
            text("UPDATE evidence_items SET submitted_by = 'worker' WHERE evidence_id = :evidence_id"),
            {"evidence_id": evidence_id},
        )


@pytest.mark.integration
async def test_case_state_versions_reject_delete(async_db_session: AsyncSession) -> None:
    _, case_id, evidence_id = await _create_case_with_evidence(async_db_session)
    bundle = await insert_case_state_bundle(
        async_db_session,
        CaseStateBundleCreate(
            state_version=CaseStateVersionCreate(
                case_id=case_id,
                version_number=1,
                trigger_evidence_id=evidence_id,
                derived_components_json={"opportunity": {"target_role": True}},
                completion_metrics_json={"completion_ratio": 0.25},
                stage_label="intake",
            ),
            evaluation_run=CaseEvaluationRunCreate(
                case_id=case_id,
                trigger_evidence_id=evidence_id,
                app_version="0.1.0",
                requirements_version="2026-03-02",
                state_machine_version="2026-03-02",
            ),
        ),
    )

    with pytest.raises(DBAPIError, match="append-only"):
        await async_db_session.execute(
            text("DELETE FROM case_state_versions WHERE case_state_version_id = :version_id"),
            {"version_id": bundle.state_version.case_state_version_id},
        )


@pytest.mark.integration
async def test_audit_events_reject_delete(async_db_session: AsyncSession) -> None:
    _, case_id, _ = await _create_case_with_evidence(async_db_session)
    audit_event = await write_audit_event(
        async_db_session,
        "case.opened",
        {"note": "created by test"},
        case_id=case_id,
    )

    with pytest.raises(DBAPIError, match="append-only"):
        await async_db_session.execute(
            text("DELETE FROM audit_events WHERE audit_event_id = :audit_event_id"),
            {"audit_event_id": audit_event.audit_event_id},
        )


@pytest.mark.integration
async def test_case_evaluation_run_unique_constraint(async_db_session: AsyncSession) -> None:
    _, case_id, evidence_id = await _create_case_with_evidence(async_db_session)
    bundle = await insert_case_state_bundle(
        async_db_session,
        CaseStateBundleCreate(
            state_version=CaseStateVersionCreate(
                case_id=case_id,
                version_number=1,
                trigger_evidence_id=evidence_id,
                derived_components_json={"opportunity": {"target_role": True}},
                completion_metrics_json={"completion_ratio": 0.25},
                stage_label="intake",
            ),
            evaluation_run=CaseEvaluationRunCreate(
                case_id=case_id,
                trigger_evidence_id=evidence_id,
                app_version="0.1.0",
                requirements_version="2026-03-02",
                state_machine_version="2026-03-02",
            ),
        ),
    )

    async_db_session.add(
        CaseEvaluationRunORM(
            case_id=case_id,
            case_state_version_id=bundle.state_version.case_state_version_id,
            trigger_evidence_id=evidence_id,
            app_version="0.1.0",
            requirements_version="2026-03-02",
            state_machine_version="2026-03-02",
        )
    )

    with pytest.raises(IntegrityError):
        await async_db_session.flush()
