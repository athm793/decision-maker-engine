"""subscriptions provider fields

Revision ID: 0002_subscriptions_provider_fields
Revises: 0001_init
Create Date: 2026-01-31
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_subscriptions_provider_fields"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Widen alembic_version.version_num in case 0001_init already ran before
    # this fix was added (the default VARCHAR(32) is too short for several IDs).
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)"))

    from sqlalchemy import inspect as sa_inspect
    inspector = sa_inspect(op.get_bind())
    existing_cols = {col["name"] for col in inspector.get_columns("subscriptions")}
    existing_idxs = {idx["name"] for idx in inspector.get_indexes("subscriptions")}

    with op.batch_alter_table("subscriptions") as batch_op:
        if "provider" not in existing_cols:
            batch_op.add_column(sa.Column("provider", sa.String(), nullable=True))
        if "provider_customer_id" not in existing_cols:
            batch_op.add_column(sa.Column("provider_customer_id", sa.String(), nullable=True))
        if "provider_subscription_id" not in existing_cols:
            batch_op.add_column(sa.Column("provider_subscription_id", sa.String(), nullable=True))
        if "provider_order_id" not in existing_cols:
            batch_op.add_column(sa.Column("provider_order_id", sa.String(), nullable=True))

        if "ix_subscriptions_provider" not in existing_idxs:
            batch_op.create_index("ix_subscriptions_provider", ["provider"])
        if "ix_subscriptions_provider_customer_id" not in existing_idxs:
            batch_op.create_index("ix_subscriptions_provider_customer_id", ["provider_customer_id"])
        if "ix_subscriptions_provider_subscription_id" not in existing_idxs:
            batch_op.create_index("ix_subscriptions_provider_subscription_id", ["provider_subscription_id"])
        if "ix_subscriptions_provider_order_id" not in existing_idxs:
            batch_op.create_index("ix_subscriptions_provider_order_id", ["provider_order_id"])


def downgrade() -> None:
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.drop_index("ix_subscriptions_provider_order_id")
        batch_op.drop_index("ix_subscriptions_provider_subscription_id")
        batch_op.drop_index("ix_subscriptions_provider_customer_id")
        batch_op.drop_index("ix_subscriptions_provider")

        batch_op.drop_column("provider_order_id")
        batch_op.drop_column("provider_subscription_id")
        batch_op.drop_column("provider_customer_id")
        batch_op.drop_column("provider")

