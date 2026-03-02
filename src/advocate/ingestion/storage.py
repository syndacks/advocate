"""Object storage helpers for raw evidence blobs."""

import asyncio
from functools import lru_cache

import boto3
from botocore.client import BaseClient

from advocate.config import settings


@lru_cache(maxsize=1)
def _s3_client() -> BaseClient:
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
    )


async def upload_blob(
    bucket: str,
    key: str,
    data: bytes,
    *,
    content_type: str | None = None,
) -> str:
    """Upload raw bytes to object storage and return the canonical S3 URI."""

    def _upload() -> None:
        extra_args: dict[str, str] = {}
        if content_type is not None:
            extra_args["ContentType"] = content_type
        _s3_client().put_object(Bucket=bucket, Key=key, Body=data, **extra_args)

    await asyncio.to_thread(_upload)
    return f"s3://{bucket}/{key}"


async def delete_blob(bucket: str, key: str) -> None:
    """Best-effort deletion for uploaded blobs after downstream failures."""

    def _delete() -> None:
        _s3_client().delete_object(Bucket=bucket, Key=key)

    await asyncio.to_thread(_delete)

