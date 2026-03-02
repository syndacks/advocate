"""Unit tests for evidence intake validation and normalization."""

from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from advocate.ingestion.router import normalize_evidence_payload, parse_metadata_json


@pytest.mark.asyncio
async def test_normalize_evidence_payload_rejects_both_file_and_text() -> None:
    upload = UploadFile(filename="note.txt", file=BytesIO(b"hello"))

    with pytest.raises(HTTPException, match="provide exactly one of file or text_content"):
        await normalize_evidence_payload(
            file=upload,
            text_content="hello",
            mime_type=None,
            filename=None,
        )


@pytest.mark.asyncio
async def test_normalize_evidence_payload_rejects_missing_payload() -> None:
    with pytest.raises(HTTPException, match="provide exactly one of file or text_content"):
        await normalize_evidence_payload(
            file=None,
            text_content=None,
            mime_type=None,
            filename=None,
        )


@pytest.mark.asyncio
async def test_normalize_evidence_payload_defaults_text_mime_type() -> None:
    payload = await normalize_evidence_payload(
        file=None,
        text_content="Recruiter follow-up email",
        mime_type=None,
        filename=None,
    )

    assert payload.mime_type == "text/plain"
    assert payload.filename == "inline.txt"
    assert payload.raw_bytes == b"Recruiter follow-up email"


def test_parse_metadata_json_requires_json_object() -> None:
    with pytest.raises(HTTPException, match="metadata_json must decode to a JSON object"):
        parse_metadata_json('["not", "an", "object"]')
