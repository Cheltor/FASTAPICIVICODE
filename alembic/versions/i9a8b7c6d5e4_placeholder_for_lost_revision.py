"""Placeholder for missing revision i9a8b7c6d5e4.

This migration records the revision ID expected by existing databases.
It does not apply schema changes because the original migration file is
not available, and affected schemas should already be up to date.

Revision ID: i9a8b7c6d5e4
Revises: b1e2c3d4f5a6
Create Date: 2025-10-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = "i9a8b7c6d5e4"
down_revision: Union[str, None] = "b1e2c3d4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op placeholder upgrade."""
    pass


def downgrade() -> None:
    """No-op placeholder downgrade."""
    pass
