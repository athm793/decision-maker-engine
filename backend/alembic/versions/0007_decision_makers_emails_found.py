"""decision makers emails_found

Revision ID: 0007_decision_makers_emails_found
Revises: 0006_jobs_cost_fields
Create Date: 2026-02-02
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_decision_makers_emails_found"
down_revision = "0006_jobs_cost_fields"
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
    if "emails_found" not in existing:
        op.add_column("decision_makers", sa.Column("emails_found", sa.Text(), nullable=True))


def downgrade() -> None:
    existing = _column_names("decision_makers")
    if "emails_found" in existing:
        op.drop_column("decision_makers", "emails_found")
