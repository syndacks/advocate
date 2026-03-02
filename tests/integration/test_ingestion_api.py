"""Integration tests for Phase 2 ingestion and timeline APIs."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from advocate.domain.models import (
    CaseEvaluationRunCreate,
    CaseStateBundleCreate,
    CaseStateVersionCreate,
)
from advocate.ingestion.events import EvidenceReceivedEvent, emit_evidence_received
from advocate.storage.orm import AuditEventORM
from advocate.storage.repositories import (
    get_latest_case_state,
    insert_case_state_bundle,
    list_case_evidence,
)


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    assert uri.startswith("s3://")
    bucket, key = uri.removeprefix("s3://").split("/", 1)
    return bucket, key


@pytest.mark.integration
async def test_post_case_evidence_file_upload_persists_blob_and_row(
    test_client: object,
    async_db_session: AsyncSession,
    create_candidate_and_case: object,
    minio_client: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    assert isinstance(test_client, httpx.AsyncClient)
    create_case = create_candidate_and_case
    assert callable(create_case)
    _, case_id = await create_case()

    async def _emit(_: object) -> UUID:
        return uuid4()

    monkeypatch.setattr("advocate.ingestion.router.emit_evidence_received", _emit)

    pdf_bytes = b"%PDF-1.4 fake pdf bytes"
    response = await test_client.post(
        f"/cases/{case_id}/evidence",
        data={
            "source_channel": "manual_ui",
            "evidence_type": "document_pdf",
            "submitted_by": "alex",
            "metadata_json": '{"origin":"upload"}',
        },
        files={
            "file": ("offer.pdf", pdf_bytes, "application/pdf"),
        },
    )

    assert response.status_code == 201
    body = response.json()
    evidence_id = UUID(body["evidence_id"])

    timeline = await list_case_evidence(async_db_session, case_id)
    evidence = next(item for item in timeline if item.evidence_id == evidence_id)
    bucket, key = _parse_s3_uri(evidence.raw_blob_uri)
    blob = minio_client.get_object(Bucket=bucket, Key=key)

    assert evidence.mime_type == "application/pdf"
    assert evidence.metadata_json == {"origin": "upload"}
    assert evidence.content_hash == "2825bfc89e1fae627faeee6aa8007367636d00604e36f711fb12b8dee3255ad5"
    assert blob["Body"].read() == pdf_bytes


@pytest.mark.integration
async def test_post_case_evidence_text_upload_defaults_text_plain_and_allows_duplicates(
    test_client: object,
    async_db_session: AsyncSession,
    create_candidate_and_case: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    assert isinstance(test_client, httpx.AsyncClient)
    create_case = create_candidate_and_case
    assert callable(create_case)
    _, case_id = await create_case()

    async def _emit(_: object) -> UUID:
        return uuid4()

    monkeypatch.setattr("advocate.ingestion.router.emit_evidence_received", _emit)

    payload = {
        "source_channel": "manual_ui",
        "evidence_type": "note_text",
        "submitted_by": "alex",
        "text_content": "same note content",
    }

    first = await test_client.post(f"/cases/{case_id}/evidence", data=payload)
    second = await test_client.post(f"/cases/{case_id}/evidence", data=payload)

    assert first.status_code == 201
    assert second.status_code == 201

    timeline = await list_case_evidence(async_db_session, case_id)
    first_id = UUID(first.json()["evidence_id"])
    second_id = UUID(second.json()["evidence_id"])
    first_row = next(item for item in timeline if item.evidence_id == first_id)
    second_row = next(item for item in timeline if item.evidence_id == second_id)

    assert first_row.mime_type == "text/plain"
    assert first_row.content_hash == second_row.content_hash
    assert first_row.raw_blob_uri != second_row.raw_blob_uri
    assert first_row.evidence_id != second_row.evidence_id


@pytest.mark.integration
async def test_post_case_evidence_returns_404_for_missing_case(
    test_client: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    assert isinstance(test_client, httpx.AsyncClient)

    async def _emit(_: object) -> UUID:
        return uuid4()

    monkeypatch.setattr("advocate.ingestion.router.emit_evidence_received", _emit)

    response = await test_client.post(
        f"/cases/{uuid4()}/evidence",
        data={
            "source_channel": "manual_ui",
            "evidence_type": "note_text",
            "submitted_by": "alex",
            "text_content": "missing case",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "case not found"


@pytest.mark.integration
async def test_post_case_evidence_dispatch_failure_returns_503_and_keeps_row(
    test_client: object,
    async_db_session: AsyncSession,
    create_candidate_and_case: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    assert isinstance(test_client, httpx.AsyncClient)
    create_case = create_candidate_and_case
    assert callable(create_case)
    _, case_id = await create_case()

    async def _emit(_: object) -> UUID:
        raise RuntimeError("prefect unavailable")

    monkeypatch.setattr("advocate.ingestion.router.emit_evidence_received", _emit)

    response = await test_client.post(
        f"/cases/{case_id}/evidence",
        data={
            "source_channel": "manual_ui",
            "evidence_type": "note_text",
            "submitted_by": "alex",
            "text_content": "dispatch should fail",
        },
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    evidence_id = UUID(detail["evidence_id"])

    timeline = await list_case_evidence(async_db_session, case_id)
    assert any(item.evidence_id == evidence_id for item in timeline)

    result = await async_db_session.execute(
        select(AuditEventORM)
        .where(AuditEventORM.case_id == case_id)
        .where(AuditEventORM.event_type == "evidence.dispatch_failed")
        .order_by(AuditEventORM.created_at.desc())
    )
    audit_event = result.scalar_one()
    assert audit_event.payload_json == {
        "evidence_id": str(evidence_id),
        "error": "prefect unavailable",
    }


@pytest.mark.integration
async def test_get_case_timeline_returns_evidence_in_received_order(
    test_client: object,
    create_candidate_and_case: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    assert isinstance(test_client, httpx.AsyncClient)
    create_case = create_candidate_and_case
    assert callable(create_case)
    _, case_id = await create_case()

    async def _emit(_: object) -> UUID:
        return uuid4()

    monkeypatch.setattr("advocate.ingestion.router.emit_evidence_received", _emit)

    earlier = datetime.now(UTC) - timedelta(hours=2)
    later = earlier + timedelta(minutes=30)

    first = await test_client.post(
        f"/cases/{case_id}/evidence",
        data={
            "source_channel": "manual_ui",
            "evidence_type": "note_text",
            "submitted_by": "alex",
            "text_content": "first event",
            "received_at": earlier.isoformat(),
        },
    )
    second = await test_client.post(
        f"/cases/{case_id}/evidence",
        data={
            "source_channel": "manual_ui",
            "evidence_type": "note_text",
            "submitted_by": "alex",
            "text_content": "second event",
            "received_at": later.isoformat(),
        },
    )
    timeline = await test_client.get(f"/cases/{case_id}/timeline")

    assert first.status_code == 201
    assert second.status_code == 201
    assert timeline.status_code == 200
    assert [item["evidence_id"] for item in timeline.json()] == [
        first.json()["evidence_id"],
        second.json()["evidence_id"],
    ]


@pytest.mark.integration
async def test_get_case_timeline_returns_empty_list_for_case_without_evidence(
    test_client: object,
    create_candidate_and_case: object,
) -> None:
    import httpx

    assert isinstance(test_client, httpx.AsyncClient)
    create_case = create_candidate_and_case
    assert callable(create_case)
    _, case_id = await create_case()

    response = await test_client.get(f"/cases/{case_id}/timeline")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.integration
async def test_get_case_state_latest_returns_404_when_case_has_no_state(
    test_client: object,
    create_candidate_and_case: object,
) -> None:
    import httpx

    assert isinstance(test_client, httpx.AsyncClient)
    create_case = create_candidate_and_case
    assert callable(create_case)
    _, case_id = await create_case()

    response = await test_client.get(f"/cases/{case_id}/state/latest")

    assert response.status_code == 404
    assert response.json()["detail"] == "case state not found"


@pytest.mark.integration
async def test_get_case_state_latest_returns_stored_version(
    test_client: object,
    async_db_session: AsyncSession,
    create_candidate_and_case: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    assert isinstance(test_client, httpx.AsyncClient)
    create_case = create_candidate_and_case
    assert callable(create_case)
    _, case_id = await create_case()

    async def _emit(_: object) -> UUID:
        return uuid4()

    monkeypatch.setattr("advocate.ingestion.router.emit_evidence_received", _emit)

    evidence_response = await test_client.post(
        f"/cases/{case_id}/evidence",
        data={
            "source_channel": "manual_ui",
            "evidence_type": "note_text",
            "submitted_by": "alex",
            "text_content": "state seed",
        },
    )
    evidence_id = UUID(evidence_response.json()["evidence_id"])

    await insert_case_state_bundle(
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
    await async_db_session.commit()

    response = await test_client.get(f"/cases/{case_id}/state/latest")
    latest_state = await get_latest_case_state(async_db_session, case_id)

    assert response.status_code == 200
    assert latest_state is not None
    assert response.json()["case_state_version_id"] == str(latest_state.case_state_version_id)
    assert response.json()["stage_label"] == "intake"


@pytest.mark.integration
async def test_emit_evidence_received_creates_real_prefect_flow_run(
    ensure_process_case_event_deployment: UUID,
) -> None:
    from prefect.client.orchestration import get_client

    assert ensure_process_case_event_deployment is not None

    event = EvidenceReceivedEvent(
        case_id=uuid4(),
        evidence_id=uuid4(),
        received_at=datetime.now(UTC),
        content_hash="abc123",
        source_channel="manual_ui",
        evidence_type="note_text",
    )

    flow_run_id = await emit_evidence_received(event)

    async with get_client() as client:
        flow_run = await client.read_flow_run(flow_run_id)

    assert flow_run.id == flow_run_id
    assert flow_run.name == f"evidence-received-{event.evidence_id}"
