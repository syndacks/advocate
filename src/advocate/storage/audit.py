"""Audit helper functions."""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from advocate.domain.models import ActorType, AuditEventCreate, AuditEventRecord
from advocate.storage.repositories import insert_audit_event


async def write_audit_event(
    session: AsyncSession,
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    case_id: UUID | None = None,
    actor_type: ActorType = ActorType.SYSTEM,
    actor_id: str = "advocate",
) -> AuditEventRecord:
    """Persist an operational audit event without committing the session."""
    return await insert_audit_event(
        session,
        AuditEventCreate(
            case_id=case_id,
            actor_type=actor_type,
            actor_id=actor_id,
            event_type=event_type,
            payload_json=payload,
        ),
    )
