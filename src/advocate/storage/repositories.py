"""Repository functions for the Phase 1 core data layer."""

from collections.abc import Sequence
from typing import TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from advocate.domain.models import (
    ArtifactCreate,
    ArtifactRecord,
    AuditEventCreate,
    AuditEventRecord,
    CandidateCreate,
    CandidateRecord,
    CaseCreate,
    CaseEvaluationRunRecord,
    CaseRecord,
    CaseStateBundleCreate,
    CaseStateBundleRecord,
    CaseStateVersionRecord,
    ComponentObservationCreate,
    ComponentObservationRecord,
    EvaluationRunInputCreate,
    EvaluationRunInputRecord,
    EvaluationRunOutputCreate,
    EvaluationRunOutputRecord,
    EvaluationRunProducerCreate,
    EvaluationRunProducerRecord,
    EvidenceItemCreate,
    EvidenceItemRecord,
)
from advocate.storage.orm import (
    ArtifactORM,
    AuditEventORM,
    CandidateORM,
    CaseEvaluationRunORM,
    CaseORM,
    CaseStateVersionORM,
    ComponentObservationORM,
    EvaluationRunInputORM,
    EvaluationRunOutputORM,
    EvaluationRunProducerORM,
    EvidenceItemORM,
)

RecordModel = TypeVar(
    "RecordModel",
    CandidateRecord,
    CaseRecord,
    EvidenceItemRecord,
    ArtifactRecord,
    ComponentObservationRecord,
    EvaluationRunInputRecord,
    EvaluationRunProducerRecord,
    EvaluationRunOutputRecord,
    AuditEventRecord,
    CaseStateVersionRecord,
    CaseEvaluationRunRecord,
)


async def _persist_and_refresh(session: AsyncSession, orm_object: object) -> None:
    session.add(orm_object)
    await session.flush()
    await session.refresh(orm_object)


def _to_record(record_type: type[RecordModel], orm_object: object) -> RecordModel:
    return record_type.model_validate(orm_object)


def _to_records(record_type: type[RecordModel], orm_objects: Sequence[object]) -> list[RecordModel]:
    return [_to_record(record_type, orm_object) for orm_object in orm_objects]


async def insert_candidate(session: AsyncSession, candidate: CandidateCreate) -> CandidateRecord:
    orm_candidate = CandidateORM(**candidate.model_dump())
    await _persist_and_refresh(session, orm_candidate)
    return _to_record(CandidateRecord, orm_candidate)


async def get_candidate(session: AsyncSession, candidate_id: UUID) -> CandidateRecord | None:
    result = await session.execute(
        select(CandidateORM).where(CandidateORM.candidate_id == candidate_id)
    )
    orm_candidate = result.scalar_one_or_none()
    if orm_candidate is None:
        return None
    return _to_record(CandidateRecord, orm_candidate)


async def insert_case(session: AsyncSession, case: CaseCreate) -> CaseRecord:
    orm_case = CaseORM(**case.model_dump())
    await _persist_and_refresh(session, orm_case)
    return _to_record(CaseRecord, orm_case)


async def get_case(session: AsyncSession, case_id: UUID) -> CaseRecord | None:
    result = await session.execute(select(CaseORM).where(CaseORM.case_id == case_id))
    orm_case = result.scalar_one_or_none()
    if orm_case is None:
        return None
    return _to_record(CaseRecord, orm_case)


async def insert_evidence(session: AsyncSession, item: EvidenceItemCreate) -> EvidenceItemRecord:
    orm_item = EvidenceItemORM(**item.model_dump())
    await _persist_and_refresh(session, orm_item)
    return _to_record(EvidenceItemRecord, orm_item)


async def list_case_evidence(session: AsyncSession, case_id: UUID) -> list[EvidenceItemRecord]:
    result = await session.execute(
        select(EvidenceItemORM)
        .where(EvidenceItemORM.case_id == case_id)
        .order_by(EvidenceItemORM.received_at.asc(), EvidenceItemORM.created_at.asc())
    )
    return _to_records(EvidenceItemRecord, result.scalars().all())


async def insert_artifact(session: AsyncSession, artifact: ArtifactCreate) -> ArtifactRecord:
    orm_artifact = ArtifactORM(**artifact.model_dump())
    await _persist_and_refresh(session, orm_artifact)
    return _to_record(ArtifactRecord, orm_artifact)


async def insert_component_observation(
    session: AsyncSession, observation: ComponentObservationCreate
) -> ComponentObservationRecord:
    orm_observation = ComponentObservationORM(**observation.model_dump())
    await _persist_and_refresh(session, orm_observation)
    return _to_record(ComponentObservationRecord, orm_observation)


async def insert_evaluation_run_input(
    session: AsyncSession, case_evaluation_run_id: UUID, evaluation_input: EvaluationRunInputCreate
) -> EvaluationRunInputRecord:
    orm_input = EvaluationRunInputORM(
        case_evaluation_run_id=case_evaluation_run_id,
        **evaluation_input.model_dump(),
    )
    await _persist_and_refresh(session, orm_input)
    return _to_record(EvaluationRunInputRecord, orm_input)


async def insert_evaluation_run_producer(
    session: AsyncSession,
    case_evaluation_run_id: UUID,
    producer: EvaluationRunProducerCreate,
) -> EvaluationRunProducerRecord:
    orm_producer = EvaluationRunProducerORM(
        case_evaluation_run_id=case_evaluation_run_id,
        **producer.model_dump(),
    )
    await _persist_and_refresh(session, orm_producer)
    return _to_record(EvaluationRunProducerRecord, orm_producer)


async def insert_evaluation_run_output(
    session: AsyncSession, case_evaluation_run_id: UUID, output: EvaluationRunOutputCreate
) -> EvaluationRunOutputRecord:
    orm_output = EvaluationRunOutputORM(
        case_evaluation_run_id=case_evaluation_run_id,
        **output.model_dump(),
    )
    await _persist_and_refresh(session, orm_output)
    return _to_record(EvaluationRunOutputRecord, orm_output)


async def insert_audit_event(
    session: AsyncSession, audit_event: AuditEventCreate
) -> AuditEventRecord:
    orm_event = AuditEventORM(**audit_event.model_dump())
    await _persist_and_refresh(session, orm_event)
    return _to_record(AuditEventRecord, orm_event)


async def insert_case_state_bundle(
    session: AsyncSession, bundle: CaseStateBundleCreate
) -> CaseStateBundleRecord:
    orm_state_version = CaseStateVersionORM(**bundle.state_version.model_dump())
    await _persist_and_refresh(session, orm_state_version)

    orm_run = CaseEvaluationRunORM(
        case_state_version_id=orm_state_version.case_state_version_id,
        **bundle.evaluation_run.model_dump(),
    )
    await _persist_and_refresh(session, orm_run)

    input_records: list[EvaluationRunInputRecord] = []
    for evaluation_input in bundle.evaluation_inputs:
        input_records.append(
            await insert_evaluation_run_input(
                session, orm_run.case_evaluation_run_id, evaluation_input
            )
        )

    producer_records: list[EvaluationRunProducerRecord] = []
    for producer in bundle.evaluation_producers:
        producer_records.append(
            await insert_evaluation_run_producer(session, orm_run.case_evaluation_run_id, producer)
        )

    output_records: list[EvaluationRunOutputRecord] = []
    for output in bundle.evaluation_outputs:
        output_records.append(
            await insert_evaluation_run_output(session, orm_run.case_evaluation_run_id, output)
        )

    return CaseStateBundleRecord(
        state_version=_to_record(CaseStateVersionRecord, orm_state_version),
        evaluation_run=_to_record(CaseEvaluationRunRecord, orm_run),
        evaluation_inputs=input_records,
        evaluation_producers=producer_records,
        evaluation_outputs=output_records,
    )


async def get_latest_case_state(
    session: AsyncSession, case_id: UUID
) -> CaseStateVersionRecord | None:
    result = await session.execute(
        select(CaseStateVersionORM)
        .where(CaseStateVersionORM.case_id == case_id)
        .order_by(CaseStateVersionORM.version_number.desc())
        .limit(1)
    )
    orm_state_version = result.scalar_one_or_none()
    if orm_state_version is None:
        return None
    return _to_record(CaseStateVersionRecord, orm_state_version)


async def get_evaluation_bundle_for_version(
    session: AsyncSession, version_id: UUID
) -> CaseStateBundleRecord | None:
    state_result = await session.execute(
        select(CaseStateVersionORM).where(CaseStateVersionORM.case_state_version_id == version_id)
    )
    orm_state_version = state_result.scalar_one_or_none()
    if orm_state_version is None:
        return None

    run_result = await session.execute(
        select(CaseEvaluationRunORM).where(CaseEvaluationRunORM.case_state_version_id == version_id)
    )
    orm_run = run_result.scalar_one_or_none()
    if orm_run is None:
        return None

    input_result = await session.execute(
        select(EvaluationRunInputORM)
        .where(EvaluationRunInputORM.case_evaluation_run_id == orm_run.case_evaluation_run_id)
        .order_by(EvaluationRunInputORM.created_at.asc())
    )
    producer_result = await session.execute(
        select(EvaluationRunProducerORM)
        .where(EvaluationRunProducerORM.case_evaluation_run_id == orm_run.case_evaluation_run_id)
        .order_by(EvaluationRunProducerORM.created_at.asc())
    )
    output_result = await session.execute(
        select(EvaluationRunOutputORM)
        .where(EvaluationRunOutputORM.case_evaluation_run_id == orm_run.case_evaluation_run_id)
        .order_by(EvaluationRunOutputORM.created_at.asc())
    )

    return CaseStateBundleRecord(
        state_version=_to_record(CaseStateVersionRecord, orm_state_version),
        evaluation_run=_to_record(CaseEvaluationRunRecord, orm_run),
        evaluation_inputs=_to_records(EvaluationRunInputRecord, input_result.scalars().all()),
        evaluation_producers=_to_records(
            EvaluationRunProducerRecord, producer_result.scalars().all()
        ),
        evaluation_outputs=_to_records(EvaluationRunOutputRecord, output_result.scalars().all()),
    )
