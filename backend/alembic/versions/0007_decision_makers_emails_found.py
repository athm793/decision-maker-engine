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
    from sqlalchemy import inspect as sa_inspect
    inspector = sa_inspect(op.get_bind())
    try:
        return {col["name"] for col in inspector.get_columns(table)}
    except Exception:
        return set()


def upgrade() -> None:
    existing = _column_names("decision_makers")
    if "emails_found" not in existing:
        op.add_column("decision_makers", sa.Column("emails_found", sa.Text(), nullable=True))


def downgrade() -> None:
    existing = _column_names("decision_makers")
    if "emails_found" in existing:
        op.drop_column("decision_makers", "emails_found")
