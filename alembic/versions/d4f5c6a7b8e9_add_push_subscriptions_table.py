"""Add push_subscriptions table for web push support

Revision ID: d4f5c6a7b8e9
Revises: f2d6c7b8a9e0
Create Date: 2025-12-03 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "d4f5c6a7b8e9"
down_revision: Union[str, None] = "f2d6c7b8a9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "push_subscriptions" not in inspector.get_table_names():
        op.create_table(
            "push_subscriptions",
            sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
            sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("endpoint", sa.Text(), nullable=False, unique=True),
            sa.Column("p256dh", sa.String(), nullable=False),
            sa.Column("auth", sa.String(), nullable=False),
            sa.Column("expiration_time", sa.BigInteger(), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index(
            op.f("ix_push_subscriptions_user_id"),
            "push_subscriptions",
            ["user_id"],
            unique=False,
        )
    else:
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("push_subscriptions")}
        if "ix_push_subscriptions_user_id" not in existing_indexes:
            op.create_index(
                op.f("ix_push_subscriptions_user_id"),
                "push_subscriptions",
                ["user_id"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "push_subscriptions" in inspector.get_table_names():
        op.drop_index(op.f("ix_push_subscriptions_user_id"), table_name="push_subscriptions")
        op.drop_table("push_subscriptions")
