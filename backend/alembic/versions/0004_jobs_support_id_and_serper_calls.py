"""jobs support id and serper calls

Revision ID: 0004_jobs_support_id_and_serper_calls
Revises: 0003_decision_makers_traces
Create Date: 2026-02-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_jobs_support_id_and_serper_calls"
down_revision = "0003_decision_makers_traces"
branch_labels = None
depends_on = None


def _column_names(table: str) -> set[str]:
    from sqlalchemy import inspect as sa_inspect
    inspector = sa_inspect(op.get_bind())
    try:
        return {col["name"] for col in inspector.get_columns(table)}
    except Exception:
        return set()


def _index_names(table: str) -> set[str]:
    from sqlalchemy import inspect as sa_inspect
    inspector = sa_inspect(op.get_bind())
    try:
        return {idx["name"] for idx in inspector.get_indexes(table)}
    except Exception:
        return set()


def upgrade() -> None:
    existing_cols = _column_names("jobs")
    existing_idx = _index_names("jobs")
    with op.batch_alter_table("jobs") as batch_op:
        if "support_id" not in existing_cols:
            batch_op.add_column(sa.Column("support_id", sa.String(), nullable=True))
        if "serper_calls" not in existing_cols:
            batch_op.add_column(sa.Column("serper_calls", sa.Integer(), nullable=True))
        if "ix_jobs_support_id" not in existing_idx:
            batch_op.create_index("ix_jobs_support_id", ["support_id"])


def downgrade() -> None:
    existing_cols = _column_names("jobs")
    existing_idx = _index_names("jobs")
    with op.batch_alter_table("jobs") as batch_op:
        if "ix_jobs_support_id" in existing_idx:
            batch_op.drop_index("ix_jobs_support_id")
        if "serper_calls" in existing_cols:
            batch_op.drop_column("serper_calls")
        if "support_id" in existing_cols:
            batch_op.drop_column("support_id")
