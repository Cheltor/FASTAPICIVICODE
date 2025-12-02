"""merge 3924 and 72 heads

Revision ID: aa41b3449d79
Revises: 3924a550dbca, 72b9a0e9b8e7
Create Date: 2025-12-01 20:04:24.111403

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa41b3449d79'
down_revision: Union[str, None] = ('3924a550dbca', '72b9a0e9b8e7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
