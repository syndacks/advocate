"""Prefect dispatch helpers for evidence ingestion events."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from prefect.client.orchestration import get_client
from pydantic import BaseModel, ConfigDict

from advocate.domain.models import EvidenceSourceChannel, EvidenceType

PROCESS_CASE_EVENT_DEPLOYMENT_NAME = "process-case-event/ingestion"


class EvidenceReceivedEvent(BaseModel):
    """Event payload emitted after evidence is durably persisted."""

    model_config = ConfigDict(extra="forbid")

    event_type: Literal["evidence.received"] = "evidence.received"
    case_id: UUID
    evidence_id: UUID
    received_at: datetime
    content_hash: str
    source_channel: EvidenceSourceChannel
    evidence_type: EvidenceType


async def emit_evidence_received(event: EvidenceReceivedEvent) -> UUID:
    """Create a Prefect flow run for downstream case processing."""
    async with get_client() as client:
        deployment = await client.read_deployment_by_name(PROCESS_CASE_EVENT_DEPLOYMENT_NAME)
        flow_run = await client.create_flow_run_from_deployment(
            deployment.id,
            parameters={
                "case_id": str(event.case_id),
                "evidence_id": str(event.evidence_id),
            },
            idempotency_key=f"evidence-received:{event.evidence_id}",
            name=f"evidence-received-{event.evidence_id}",
            tags=[
                f"case:{event.case_id}",
                f"evidence:{event.evidence_id}",
                "ingestion",
            ],
        )
    return flow_run.id
