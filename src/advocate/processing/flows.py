"""Prefect flow scaffolding for Phase 2 ingestion dispatch."""

from uuid import UUID

from prefect import flow


@flow(name="process-case-event")
async def process_case_event(case_id: UUID, evidence_id: UUID) -> None:
    """Phase 2 stub flow invoked after evidence ingestion."""
    del case_id, evidence_id
