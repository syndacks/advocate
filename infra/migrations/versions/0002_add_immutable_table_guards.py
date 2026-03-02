"""Add immutability guards for append-only tables.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-02
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

IMMUTABLE_TABLES = [
    "evidence_items",
    "artifacts",
    "component_observations",
    "case_state_versions",
    "case_evaluation_runs",
    "evaluation_run_inputs",
    "evaluation_run_producers",
    "evaluation_run_outputs",
    "audit_events",
    "retrieval_chunks",
]


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_immutable_table_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Table % is append-only; % is not allowed', TG_TABLE_NAME, TG_OP;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    for table_name in IMMUTABLE_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_prevent_{table_name}_mutation
            BEFORE UPDATE OR DELETE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION prevent_immutable_table_mutation()
            """
        )


def downgrade() -> None:
    for table_name in IMMUTABLE_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_prevent_{table_name}_mutation ON {table_name}")

    op.execute("DROP FUNCTION IF EXISTS prevent_immutable_table_mutation()")
