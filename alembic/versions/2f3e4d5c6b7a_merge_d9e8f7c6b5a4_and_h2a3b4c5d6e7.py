"""Merge heads: d9e8f7c6b5a4 and h2a3b4c5d6e7

Revision ID: 2f3e4d5c6b7a
Revises: d9e8f7c6b5a4, h2a3b4c5d6e7
Create Date: 2025-10-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f3e4d5c6b7a'
down_revision: Union[tuple[str, str], None] = ('d9e8f7c6b5a4', 'h2a3b4c5d6e7')
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """This is an empty merge revision to resolve multiple heads.

    No schema changes are required; this file simply records the merge.
    """
    pass


def downgrade() -> None:
    # Downgrade is a no-op for the merge revision.
    pass
