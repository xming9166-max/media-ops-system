"""create account and account_history

Revision ID: 63d1017e6124
Revises:
Create Date: 2026-09-04 15:21:50.042766

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "63d1017e6124"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 账号主表(只存活跃记录)
    op.create_table(
        "account",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("business_key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_key", name="uq_account_business_key"),
    )
    op.create_index("ix_account_business_key", "account", ["business_key"])

    # 账号历史表(<主表名>_history;业务列无唯一约束,append-only)
    op.create_table(
        "account_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("business_key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=False),
        sa.Column("delete_reason", sa.String(256), nullable=True),
        sa.Column("restored_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_history_source_id", "account_history", ["source_id"])
    op.create_index("ix_account_history_restored_at", "account_history", ["restored_at"])
    op.create_index("ix_archive_source_deleted", "account_history", ["source_id", "deleted_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_archive_source_deleted", table_name="account_history")
    op.drop_index("ix_account_history_restored_at", table_name="account_history")
    op.drop_index("ix_account_history_source_id", table_name="account_history")
    op.drop_table("account_history")
    op.drop_index("ix_account_business_key", table_name="account")
    op.drop_table("account")
