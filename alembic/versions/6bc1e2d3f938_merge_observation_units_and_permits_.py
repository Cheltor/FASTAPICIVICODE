"""Merge observation/units and permits branches

Revision ID: 6bc1e2d3f938
Revises: a1b2c3d4e5f6, e7c9a1b2c3d4
Create Date: 2025-09-07 12:52:12.128006

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6bc1e2d3f938'
down_revision: Union[str, None] = ('a1b2c3d4e5f6', 'e7c9a1b2c3d4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
