"""decision makers company meta

Revision ID: 0008_decision_makers_company_meta
Revises: 0007_decision_makers_emails_found
Create Date: 2026-02-02
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_decision_makers_company_meta"
down_revision = "0007_decision_makers_emails_found"
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
    if "company_address" not in existing:
        op.add_column("decision_makers", sa.Column("company_address", sa.Text(), nullable=True))
    if "gmaps_rating" not in existing:
        op.add_column("decision_makers", sa.Column("gmaps_rating", sa.Float(), nullable=True))
    if "gmaps_reviews" not in existing:
        op.add_column("decision_makers", sa.Column("gmaps_reviews", sa.Integer(), nullable=True))


def downgrade() -> None:
    existing = _column_names("decision_makers")
    if "gmaps_reviews" in existing:
        op.drop_column("decision_makers", "gmaps_reviews")
    if "gmaps_rating" in existing:
        op.drop_column("decision_makers", "gmaps_rating")
    if "company_address" in existing:
        op.drop_column("decision_makers", "company_address")

