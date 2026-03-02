"""FastAPI router for Phase 2 evidence ingestion and timeline reads."""

import json
from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from advocate.config import settings
from advocate.domain.models import (
    CaseStateVersionRecord,
    EvidenceItemCreate,
    EvidenceItemRecord,
    EvidenceSourceChannel,
    EvidenceType,
)
from advocate.ingestion.events import EvidenceReceivedEvent, emit_evidence_received
from advocate.ingestion.hashing import content_hash
from advocate.ingestion.storage import delete_blob, upload_blob
from advocate.storage.audit import write_audit_event
from advocate.storage.db import AsyncSessionFactory, get_session
from advocate.storage.repositories import (
    get_case,
    get_latest_case_state,
    insert_evidence,
    list_case_evidence,
)

router = APIRouter()


class EvidenceUploadResponse(BaseModel):
    """API response for successful evidence ingestion."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: UUID
    case_id: UUID
    received_at: datetime


class NormalizedEvidencePayload(BaseModel):
    """Validated evidence payload ready for hashing and upload."""

    model_config = ConfigDict(extra="forbid")

    raw_bytes: bytes
    filename: str
    mime_type: str


def parse_metadata_json(metadata_json: str | None) -> dict[str, object] | None:
    """Parse a JSON object encoded in a form field."""
    if metadata_json is None:
        return None
    try:
        parsed = json.loads(metadata_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="metadata_json must be valid JSON",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="metadata_json must decode to a JSON object",
        )
    return parsed


async def normalize_evidence_payload(
    *,
    file: UploadFile | None,
    text_content: str | None,
    mime_type: str | None,
    filename: str | None,
) -> NormalizedEvidencePayload:
    """Validate the request body and normalize it into raw bytes plus metadata."""
    has_file = file is not None
    has_text = text_content is not None

    if has_file == has_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="provide exactly one of file or text_content",
        )

    if file is not None:
        raw_bytes = await file.read()
        if not raw_bytes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="uploaded file must not be empty",
            )
        effective_filename = file.filename or "upload.bin"
        effective_mime_type = mime_type or file.content_type or "application/octet-stream"
        return NormalizedEvidencePayload(
            raw_bytes=raw_bytes,
            filename=effective_filename,
            mime_type=effective_mime_type,
        )

    assert text_content is not None
    if not text_content.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="text_content must not be blank",
        )
    return NormalizedEvidencePayload(
        raw_bytes=text_content.encode("utf-8"),
        filename=filename or "inline.txt",
        mime_type=mime_type or "text/plain",
    )


def build_blob_key(case_id: UUID, received_at: datetime, filename: str) -> str:
    """Build a unique object storage key for the uploaded evidence payload."""
    suffix = Path(filename).suffix.lower()
    return (
        f"cases/{case_id}/evidence/{received_at:%Y/%m/%d}/"
        f"{uuid4()}{suffix}"
    )


async def _record_dispatch_failure(case_id: UUID, evidence_id: UUID, error: str) -> None:
    try:
        async with AsyncSessionFactory() as session:
            await write_audit_event(
                session,
                "evidence.dispatch_failed",
                {
                    "evidence_id": str(evidence_id),
                    "error": error,
                },
                case_id=case_id,
            )
            await session.commit()
    except Exception:
        pass


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency wrapper used to satisfy lint rules on Depends."""
    async for session in get_session():
        yield session


@router.post(
    "/cases/{case_id}/evidence",
    response_model=EvidenceUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_case_evidence(
    case_id: UUID,
    source_channel: Annotated[EvidenceSourceChannel, Form(...)],
    evidence_type: Annotated[EvidenceType, Form(...)],
    submitted_by: Annotated[str, Form(..., min_length=1)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    file: Annotated[UploadFile | None, File()] = None,
    text_content: Annotated[str | None, Form()] = None,
    source_ref: Annotated[str | None, Form()] = None,
    received_at: Annotated[datetime | None, Form()] = None,
    mime_type: Annotated[str | None, Form()] = None,
    filename: Annotated[str | None, Form()] = None,
    metadata_json: Annotated[str | None, Form()] = None,
) -> EvidenceUploadResponse:
    case = await get_case(session, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")

    parsed_metadata = parse_metadata_json(metadata_json)
    normalized_payload = await normalize_evidence_payload(
        file=file,
        text_content=text_content,
        mime_type=mime_type,
        filename=filename,
    )
    effective_received_at = received_at or datetime.now(UTC)
    blob_key = build_blob_key(case_id, effective_received_at, normalized_payload.filename)
    raw_blob_uri = await upload_blob(
        settings.s3_bucket,
        blob_key,
        normalized_payload.raw_bytes,
        content_type=normalized_payload.mime_type,
    )

    try:
        evidence = await insert_evidence(
            session,
            EvidenceItemCreate(
                case_id=case_id,
                source_channel=source_channel,
                source_ref=source_ref,
                mime_type=normalized_payload.mime_type,
                evidence_type=evidence_type,
                received_at=effective_received_at,
                content_hash=content_hash(normalized_payload.raw_bytes),
                raw_blob_uri=raw_blob_uri,
                submitted_by=submitted_by,
                metadata_json=parsed_metadata,
            ),
        )
        await session.commit()
    except Exception as exc:
        await session.rollback()
        with suppress(Exception):
            await delete_blob(settings.s3_bucket, blob_key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="failed to persist evidence",
        ) from exc

    event = EvidenceReceivedEvent(
        case_id=evidence.case_id,
        evidence_id=evidence.evidence_id,
        received_at=evidence.received_at,
        content_hash=evidence.content_hash,
        source_channel=evidence.source_channel,
        evidence_type=evidence.evidence_type,
    )

    try:
        await emit_evidence_received(event)
    except Exception as exc:
        await _record_dispatch_failure(case_id, evidence.evidence_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "evidence stored but downstream dispatch failed",
                "evidence_id": str(evidence.evidence_id),
            },
        ) from exc

    return EvidenceUploadResponse(
        evidence_id=evidence.evidence_id,
        case_id=evidence.case_id,
        received_at=evidence.received_at,
    )


@router.get("/cases/{case_id}/timeline", response_model=list[EvidenceItemRecord])
async def get_case_timeline(
    case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[EvidenceItemRecord]:
    case = await get_case(session, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
    return await list_case_evidence(session, case_id)


@router.get("/cases/{case_id}/state/latest", response_model=CaseStateVersionRecord)
async def get_latest_case_state_version(
    case_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CaseStateVersionRecord:
    case = await get_case(session, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")

    latest_state = await get_latest_case_state(session, case_id)
    if latest_state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="case state not found",
        )
    return latest_state
