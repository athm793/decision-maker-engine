"""jobs llm token counters

Revision ID: 0005_jobs_llm_token_counters
Revises: 0004_jobs_support_id_and_serper_calls
Create Date: 2026-02-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_jobs_llm_token_counters"
down_revision = "0004_jobs_support_id_and_serper_calls"
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
        if "llm_prompt_tokens" not in existing:
            batch_op.add_column(sa.Column("llm_prompt_tokens", sa.Integer(), nullable=True))
        if "llm_completion_tokens" not in existing:
            batch_op.add_column(sa.Column("llm_completion_tokens", sa.Integer(), nullable=True))
        if "llm_total_tokens" not in existing:
            batch_op.add_column(sa.Column("llm_total_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    existing = _column_names("jobs")
    with op.batch_alter_table("jobs") as batch_op:
        if "llm_total_tokens" in existing:
            batch_op.drop_column("llm_total_tokens")
        if "llm_completion_tokens" in existing:
            batch_op.drop_column("llm_completion_tokens")
        if "llm_prompt_tokens" in existing:
            batch_op.drop_column("llm_prompt_tokens")
