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
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    names: set[str] = set()
    for r in rows:
        try:
            names.add(str(r[1]))
        except Exception:
            continue
    return names


def _index_names(table: str) -> set[str]:
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"PRAGMA index_list({table})")).fetchall()
    names: set[str] = set()
    for r in rows:
        try:
            names.add(str(r[1]))
        except Exception:
            continue
    return names


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
