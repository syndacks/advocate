"""Prefect deployment registration for worker flows."""

import asyncio
from uuid import UUID

from prefect import flow

from advocate.config import settings
from advocate.processing.flows import process_case_event


@flow(name="noop")
async def noop_flow() -> str:
    """No-op flow used to verify worker and Prefect connectivity."""
    return "ok"


async def ensure_process_case_event_deployment() -> UUID:
    """Create or update the ingestion deployment used by the API."""
    deployment = await process_case_event.to_deployment(
        name="ingestion",
        version=settings.app_version,
        tags=["ingestion"],
    )
    return await deployment.aapply()


if __name__ == "__main__":
    asyncio.run(ensure_process_case_event_deployment())
