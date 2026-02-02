"""decision makers trace timestamps

Revision ID: 0009_decision_makers_trace_timestamps
Revises: 0008_decision_makers_company_meta
Create Date: 2026-02-02
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_decision_makers_trace_timestamps"
down_revision = "0008_decision_makers_company_meta"
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
    if "llm_call_timestamp" not in existing:
        op.add_column("decision_makers", sa.Column("llm_call_timestamp", sa.DateTime(timezone=True), nullable=True))
    if "serper_call_timestamp" not in existing:
        op.add_column("decision_makers", sa.Column("serper_call_timestamp", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    existing = _column_names("decision_makers")
    if "serper_call_timestamp" in existing:
        op.drop_column("decision_makers", "serper_call_timestamp")
    if "llm_call_timestamp" in existing:
        op.drop_column("decision_makers", "llm_call_timestamp")

