"""decision makers traces

Revision ID: 0003_decision_makers_traces
Revises: 0002_subscriptions_provider_fields
Create Date: 2026-02-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_decision_makers_traces"
down_revision = "0002_subscriptions_provider_fields"
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


def upgrade() -> None:
    existing = _column_names("decision_makers")
    with op.batch_alter_table("decision_makers") as batch_op:
        if "llm_input" not in existing:
            batch_op.add_column(sa.Column("llm_input", sa.Text(), nullable=True))
        if "serper_queries" not in existing:
            batch_op.add_column(sa.Column("serper_queries", sa.Text(), nullable=True))
        if "llm_output" not in existing:
            batch_op.add_column(sa.Column("llm_output", sa.Text(), nullable=True))


def downgrade() -> None:
    existing = _column_names("decision_makers")
    with op.batch_alter_table("decision_makers") as batch_op:
        if "llm_output" in existing:
            batch_op.drop_column("llm_output")
        if "serper_queries" in existing:
            batch_op.drop_column("serper_queries")
        if "llm_input" in existing:
            batch_op.drop_column("llm_input")
