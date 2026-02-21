"""init

Revision ID: 0001_init
Revises:
Create Date: 2026-01-31
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def _inspector():
    from sqlalchemy import inspect as sa_inspect
    return sa_inspect(op.get_bind())


def upgrade() -> None:
    # Alembic creates alembic_version with version_num VARCHAR(32) by default,
    # which is too short for some revision IDs in this project. Widen it early.
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)"))

    inspector = _inspector()
    existing_tables = set(inspector.get_table_names())

    def existing_indexes(table: str) -> set[str]:
        if table not in existing_tables:
            return set()
        return {idx["name"] for idx in inspector.get_indexes(table)}

    if "profiles" not in existing_tables:
        op.create_table(
            "profiles",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("email", sa.String(), nullable=True),
            sa.Column("work_email", sa.String(), nullable=True),
            sa.Column("first_name", sa.String(), nullable=True),
            sa.Column("last_name", sa.String(), nullable=True),
            sa.Column("company_name", sa.String(), nullable=True),
            sa.Column("role", sa.String(), nullable=True),
            sa.Column("signup_ip", sa.String(), nullable=True),
            sa.Column("last_ip", sa.String(), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)")),
        )
    idxs = existing_indexes("profiles")
    if "ix_profiles_id" not in idxs:
        op.create_index("ix_profiles_id", "profiles", ["id"])
    if "ix_profiles_email" not in idxs:
        op.create_index("ix_profiles_email", "profiles", ["email"])
    if "ix_profiles_work_email" not in idxs:
        op.create_index("ix_profiles_work_email", "profiles", ["work_email"])
    if "ix_profiles_role" not in idxs:
        op.create_index("ix_profiles_role", "profiles", ["role"])

    if "jobs" not in existing_tables:
        op.create_table(
            "jobs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("filename", sa.String(), nullable=True),
            sa.Column("status", sa.Enum("queued", "processing", "completed", "failed", "cancelled", name="jobstatus"), nullable=True),
            sa.Column("total_companies", sa.Integer(), nullable=True),
            sa.Column("processed_companies", sa.Integer(), nullable=True),
            sa.Column("decision_makers_found", sa.Integer(), nullable=True),
            sa.Column("llm_calls_started", sa.Integer(), nullable=True),
            sa.Column("llm_calls_succeeded", sa.Integer(), nullable=True),
            sa.Column("column_mappings", sa.JSON(), nullable=True),
            sa.Column("companies_data", sa.JSON(), nullable=True),
            sa.Column("selected_platforms", sa.JSON(), nullable=True),
            sa.Column("max_contacts_total", sa.Integer(), nullable=True),
            sa.Column("max_contacts_per_company", sa.Integer(), nullable=True),
            sa.Column("credits_spent", sa.Integer(), nullable=True),
            sa.Column("stop_reason", sa.String(), nullable=True),
            sa.Column("options", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
    idxs = existing_indexes("jobs")
    if "ix_jobs_id" not in idxs:
        op.create_index("ix_jobs_id", "jobs", ["id"])
    if "ix_jobs_user_id" not in idxs:
        op.create_index("ix_jobs_user_id", "jobs", ["user_id"])
    if "ix_jobs_filename" not in idxs:
        op.create_index("ix_jobs_filename", "jobs", ["filename"])

    if "decision_makers" not in existing_tables:
        op.create_table(
            "decision_makers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("job_id", sa.Integer(), nullable=True),
            sa.Column("company_name", sa.String(), nullable=True),
            sa.Column("company_type", sa.String(), nullable=True),
            sa.Column("company_city", sa.String(), nullable=True),
            sa.Column("company_country", sa.String(), nullable=True),
            sa.Column("company_website", sa.String(), nullable=True),
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("title", sa.String(), nullable=True),
            sa.Column("platform", sa.String(), nullable=True),
            sa.Column("profile_url", sa.String(), nullable=True),
            sa.Column("confidence_score", sa.String(), nullable=True),
            sa.Column("reasoning", sa.Text(), nullable=True),
            sa.Column("uploaded_company_data", sa.Text(), nullable=True),
        )
    idxs = existing_indexes("decision_makers")
    if "ix_decision_makers_id" not in idxs:
        op.create_index("ix_decision_makers_id", "decision_makers", ["id"])
    if "ix_decision_makers_user_id" not in idxs:
        op.create_index("ix_decision_makers_user_id", "decision_makers", ["user_id"])
    if "ix_decision_makers_company_name" not in idxs:
        op.create_index("ix_decision_makers_company_name", "decision_makers", ["company_name"])

    if "credit_accounts" not in existing_tables:
        op.create_table(
            "credit_accounts",
            sa.Column("user_id", sa.String(), primary_key=True),
            sa.Column("balance", sa.Integer(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        )
    idxs = existing_indexes("credit_accounts")
    if "ix_credit_accounts_user_id" not in idxs:
        op.create_index("ix_credit_accounts_user_id", "credit_accounts", ["user_id"])

    if "credit_ledger" not in existing_tables:
        op.create_table(
            "credit_ledger",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("lot_id", sa.String(), nullable=True),
            sa.Column("event_type", sa.String(), nullable=True),
            sa.Column("delta", sa.Integer(), nullable=True),
            sa.Column("source", sa.String(), nullable=True),
            sa.Column("job_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)")),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
        )
    idxs = existing_indexes("credit_ledger")
    if "ix_credit_ledger_id" not in idxs:
        op.create_index("ix_credit_ledger_id", "credit_ledger", ["id"])
    if "ix_credit_ledger_user_id" not in idxs:
        op.create_index("ix_credit_ledger_user_id", "credit_ledger", ["user_id"])
    if "ix_credit_ledger_lot_id" not in idxs:
        op.create_index("ix_credit_ledger_lot_id", "credit_ledger", ["lot_id"])
    if "ix_credit_ledger_event_type" not in idxs:
        op.create_index("ix_credit_ledger_event_type", "credit_ledger", ["event_type"])
    if "ix_credit_ledger_source" not in idxs:
        op.create_index("ix_credit_ledger_source", "credit_ledger", ["source"])
    if "ix_credit_ledger_job_id" not in idxs:
        op.create_index("ix_credit_ledger_job_id", "credit_ledger", ["job_id"])

    if "subscriptions" not in existing_tables:
        op.create_table(
            "subscriptions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("plan_key", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
            sa.Column("stripe_customer_id", sa.String(), nullable=True),
            sa.Column("stripe_subscription_id", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        )
    idxs = existing_indexes("subscriptions")
    if "ix_subscriptions_id" not in idxs:
        op.create_index("ix_subscriptions_id", "subscriptions", ["id"])
    if "ix_subscriptions_user_id" not in idxs:
        op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"], unique=True)

    if "coupon_codes" not in existing_tables:
        op.create_table(
            "coupon_codes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(), nullable=True),
            sa.Column("coupon_type", sa.String(), nullable=True),
            sa.Column("active", sa.Integer(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)")),
        )
    idxs = existing_indexes("coupon_codes")
    if "ix_coupon_codes_id" not in idxs:
        op.create_index("ix_coupon_codes_id", "coupon_codes", ["id"])
    if "ix_coupon_codes_code" not in idxs:
        op.create_index("ix_coupon_codes_code", "coupon_codes", ["code"], unique=True)

    if "coupon_assignments" not in existing_tables:
        op.create_table(
            "coupon_assignments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("coupon_code_id", sa.Integer(), nullable=True),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)")),
            sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        )
    idxs = existing_indexes("coupon_assignments")
    if "ix_coupon_assignments_id" not in idxs:
        op.create_index("ix_coupon_assignments_id", "coupon_assignments", ["id"])
    if "ix_coupon_assignments_coupon_code_id" not in idxs:
        op.create_index("ix_coupon_assignments_coupon_code_id", "coupon_assignments", ["coupon_code_id"])
    if "ix_coupon_assignments_user_id" not in idxs:
        op.create_index("ix_coupon_assignments_user_id", "coupon_assignments", ["user_id"])

    if "support_conversations" not in existing_tables:
        op.create_table(
            "support_conversations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)")),
        )
    idxs = existing_indexes("support_conversations")
    if "ix_support_conversations_id" not in idxs:
        op.create_index("ix_support_conversations_id", "support_conversations", ["id"])
    if "ix_support_conversations_user_id" not in idxs:
        op.create_index("ix_support_conversations_user_id", "support_conversations", ["user_id"])
    if "ix_support_conversations_status" not in idxs:
        op.create_index("ix_support_conversations_status", "support_conversations", ["status"])

    if "support_messages" not in existing_tables:
        op.create_table(
            "support_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("conversation_id", sa.Integer(), nullable=True),
            sa.Column("sender_role", sa.String(), nullable=True),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)")),
        )
    idxs = existing_indexes("support_messages")
    if "ix_support_messages_id" not in idxs:
        op.create_index("ix_support_messages_id", "support_messages", ["id"])
    if "ix_support_messages_conversation_id" not in idxs:
        op.create_index("ix_support_messages_conversation_id", "support_messages", ["conversation_id"])
    if "ix_support_messages_sender_role" not in idxs:
        op.create_index("ix_support_messages_sender_role", "support_messages", ["sender_role"])


def downgrade() -> None:
    op.drop_index("ix_support_messages_sender_role", table_name="support_messages")
    op.drop_index("ix_support_messages_conversation_id", table_name="support_messages")
    op.drop_index("ix_support_messages_id", table_name="support_messages")
    op.drop_table("support_messages")

    op.drop_index("ix_support_conversations_status", table_name="support_conversations")
    op.drop_index("ix_support_conversations_user_id", table_name="support_conversations")
    op.drop_index("ix_support_conversations_id", table_name="support_conversations")
    op.drop_table("support_conversations")

    op.drop_index("ix_coupon_assignments_user_id", table_name="coupon_assignments")
    op.drop_index("ix_coupon_assignments_coupon_code_id", table_name="coupon_assignments")
    op.drop_index("ix_coupon_assignments_id", table_name="coupon_assignments")
    op.drop_table("coupon_assignments")

    op.drop_index("ix_coupon_codes_code", table_name="coupon_codes")
    op.drop_index("ix_coupon_codes_id", table_name="coupon_codes")
    op.drop_table("coupon_codes")

    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_id", table_name="subscriptions")
    op.drop_table("subscriptions")

    op.drop_index("ix_credit_ledger_job_id", table_name="credit_ledger")
    op.drop_index("ix_credit_ledger_source", table_name="credit_ledger")
    op.drop_index("ix_credit_ledger_event_type", table_name="credit_ledger")
    op.drop_index("ix_credit_ledger_lot_id", table_name="credit_ledger")
    op.drop_index("ix_credit_ledger_user_id", table_name="credit_ledger")
    op.drop_index("ix_credit_ledger_id", table_name="credit_ledger")
    op.drop_table("credit_ledger")

    op.drop_index("ix_credit_accounts_user_id", table_name="credit_accounts")
    op.drop_table("credit_accounts")

    op.drop_index("ix_decision_makers_company_name", table_name="decision_makers")
    op.drop_index("ix_decision_makers_user_id", table_name="decision_makers")
    op.drop_index("ix_decision_makers_id", table_name="decision_makers")
    op.drop_table("decision_makers")

    op.drop_index("ix_jobs_filename", table_name="jobs")
    op.drop_index("ix_jobs_user_id", table_name="jobs")
    op.drop_index("ix_jobs_id", table_name="jobs")
    op.drop_table("jobs")
    sa.Enum(name="jobstatus").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_profiles_role", table_name="profiles")
    op.drop_index("ix_profiles_work_email", table_name="profiles")
    op.drop_index("ix_profiles_email", table_name="profiles")
    op.drop_index("ix_profiles_id", table_name="profiles")
    op.drop_table("profiles")
