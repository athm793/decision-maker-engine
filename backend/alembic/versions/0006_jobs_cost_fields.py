"""jobs cost fields

Revision ID: 0006_jobs_cost_fields
Revises: 0005_jobs_llm_token_counters
Create Date: 2026-02-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_jobs_cost_fields"
down_revision = "0005_jobs_llm_token_counters"
branch_labels = None
depends_on = None


def _column_names(table: str) -> set[str]:
    from sqlalchemy import inspect as sa_inspect
    inspector = sa_inspect(op.get_bind())
    try:
        return {col["name"] for col in inspector.get_columns(table)}
    except Exception:
        return set()


def upgrade() -> None:
    existing = _column_names("jobs")
    with op.batch_alter_table("jobs") as batch_op:
        if "llm_cost_usd" not in existing:
            batch_op.add_column(sa.Column("llm_cost_usd", sa.Float(), nullable=True))
        if "serper_cost_usd" not in existing:
            batch_op.add_column(sa.Column("serper_cost_usd", sa.Float(), nullable=True))
        if "total_cost_usd" not in existing:
            batch_op.add_column(sa.Column("total_cost_usd", sa.Float(), nullable=True))
        if "cost_per_contact_usd" not in existing:
            batch_op.add_column(sa.Column("cost_per_contact_usd", sa.Float(), nullable=True))


def downgrade() -> None:
    existing = _column_names("jobs")
    with op.batch_alter_table("jobs") as batch_op:
        if "cost_per_contact_usd" in existing:
            batch_op.drop_column("cost_per_contact_usd")
        if "total_cost_usd" in existing:
            batch_op.drop_column("total_cost_usd")
        if "serper_cost_usd" in existing:
            batch_op.drop_column("serper_cost_usd")
        if "llm_cost_usd" in existing:
            batch_op.drop_column("llm_cost_usd")
