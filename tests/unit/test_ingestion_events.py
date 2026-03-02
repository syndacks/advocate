"""Unit tests for Prefect ingestion dispatch."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from advocate.domain.models import EvidenceSourceChannel, EvidenceType
from advocate.ingestion.events import (
    PROCESS_CASE_EVENT_DEPLOYMENT_NAME,
    EvidenceReceivedEvent,
    emit_evidence_received,
)


class _FakeClient:
    def __init__(self) -> None:
        self.deployment_name: str | None = None
        self.create_kwargs: dict[str, object] | None = None

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def read_deployment_by_name(self, deployment_name: str) -> SimpleNamespace:
        self.deployment_name = deployment_name
        return SimpleNamespace(id=uuid4())

    async def create_flow_run_from_deployment(
        self,
        deployment_id: object,
        **kwargs: object,
    ) -> SimpleNamespace:
        self.create_kwargs = {"deployment_id": deployment_id, **kwargs}
        return SimpleNamespace(id=uuid4())


@pytest.mark.asyncio
async def test_emit_evidence_received_uses_expected_prefect_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeClient()
    monkeypatch.setattr(
        "advocate.ingestion.events.get_client",
        lambda: fake_client,
    )

    case_id = uuid4()
    evidence_id = uuid4()
    event = EvidenceReceivedEvent(
        case_id=case_id,
        evidence_id=evidence_id,
        received_at=datetime.now(UTC),
        content_hash="abc123",
        source_channel=EvidenceSourceChannel.MANUAL_UI,
        evidence_type=EvidenceType.NOTE_TEXT,
    )

    await emit_evidence_received(event)

    assert fake_client.deployment_name == PROCESS_CASE_EVENT_DEPLOYMENT_NAME
    assert fake_client.create_kwargs is not None
    assert fake_client.create_kwargs["parameters"] == {
        "case_id": str(case_id),
        "evidence_id": str(evidence_id),
    }
    assert fake_client.create_kwargs["idempotency_key"] == f"evidence-received:{evidence_id}"
    assert fake_client.create_kwargs["name"] == f"evidence-received-{evidence_id}"
