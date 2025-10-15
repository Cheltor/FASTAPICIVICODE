"""merge heads

Revision ID: 1e6779f87a6b
Revises: 4fe31378a9aa, b1e2c3d4f5a6
Create Date: 2025-10-14 20:25:45.675463

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e6779f87a6b'
# This is a merge revision that combines two heads
down_revision: Union[tuple[str, str], None] = ('4fe31378a9aa', 'b1e2c3d4f5a6')
branch_labels: Union[str, Sequence[str], None] = ('merge',)
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
