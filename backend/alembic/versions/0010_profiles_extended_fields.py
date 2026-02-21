"""profiles extended fields

Revision ID: 0010_profiles_extended_fields
Revises: 0009_decision_makers_trace_timestamps
Create Date: 2026-02-21
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_profiles_extended_fields"
down_revision = "0009_decision_makers_trace_timestamps"
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
    existing_cols = _column_names("profiles")
    if "work_email" not in existing_cols:
        op.add_column("profiles", sa.Column("work_email", sa.String(), nullable=True))
    if "first_name" not in existing_cols:
        op.add_column("profiles", sa.Column("first_name", sa.String(), nullable=True))
    if "last_name" not in existing_cols:
        op.add_column("profiles", sa.Column("last_name", sa.String(), nullable=True))
    if "company_name" not in existing_cols:
        op.add_column("profiles", sa.Column("company_name", sa.String(), nullable=True))
    if "signup_ip" not in existing_cols:
        op.add_column("profiles", sa.Column("signup_ip", sa.String(), nullable=True))
    if "last_ip" not in existing_cols:
        op.add_column("profiles", sa.Column("last_ip", sa.String(), nullable=True))
    if "last_seen_at" not in existing_cols:
        op.add_column("profiles", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))

    existing_idxs = _index_names("profiles")
    if "ix_profiles_work_email" not in existing_idxs:
        op.create_index("ix_profiles_work_email", "profiles", ["work_email"])
    if "ix_profiles_role" not in existing_idxs:
        op.create_index("ix_profiles_role", "profiles", ["role"])


def downgrade() -> None:
    existing_idxs = _index_names("profiles")
    if "ix_profiles_role" in existing_idxs:
        op.drop_index("ix_profiles_role", table_name="profiles")
    if "ix_profiles_work_email" in existing_idxs:
        op.drop_index("ix_profiles_work_email", table_name="profiles")

    existing_cols = _column_names("profiles")
    if "last_seen_at" in existing_cols:
        op.drop_column("profiles", "last_seen_at")
    if "last_ip" in existing_cols:
        op.drop_column("profiles", "last_ip")
    if "signup_ip" in existing_cols:
        op.drop_column("profiles", "signup_ip")
    if "company_name" in existing_cols:
        op.drop_column("profiles", "company_name")
    if "last_name" in existing_cols:
        op.drop_column("profiles", "last_name")
    if "first_name" in existing_cols:
        op.drop_column("profiles", "first_name")
    if "work_email" in existing_cols:
        op.drop_column("profiles", "work_email")
