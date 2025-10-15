"""Add comment_id to notifications (safe, idempotent)

Revision ID: h2a3b4c5d6e7
Revises: 1e6779f87a6b
Create Date: 2025-10-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "h2a3b4c5d6e7"
down_revision: Union[str, None] = "1e6779f87a6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    try:
        return table_name in _insp().get_table_names()
    except Exception:
        return False


def _has_column(table_name: str, column_name: str) -> bool:
    try:
        return any(c.get("name") == column_name for c in _insp().get_columns(table_name))
    except Exception:
        return False


def _has_index(table_name: str, index_name: str) -> bool:
    try:
        return any(ix.get("name") == index_name for ix in _insp().get_indexes(table_name))
    except Exception:
        return False


def upgrade() -> None:
    # Add notifications.comment_id if missing
    if _has_table("notifications") and not _has_column("notifications", "comment_id"):
        op.add_column("notifications", sa.Column("comment_id", sa.BigInteger(), nullable=True))

    # Create a non-unique index on comment_id for lookup speed (optional)
    if _has_table("notifications") and _has_column("notifications", "comment_id"):
        idx_name = "index_notifications_on_comment_id"
        if not _has_index("notifications", idx_name):
            op.create_index(idx_name, "notifications", ["comment_id"], unique=False)


def downgrade() -> None:
    # Drop index first if present
    if _has_table("notifications") and _has_index("notifications", "index_notifications_on_comment_id"):
        op.drop_index("index_notifications_on_comment_id", table_name="notifications")

    # Then drop the column if present
    if _has_table("notifications") and _has_column("notifications", "comment_id"):
        op.drop_column("notifications", "comment_id")
