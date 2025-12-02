"""add closed_at to violations

Revision ID: 8896e4853365
Revises: aa41b3449d79
Create Date: 2025-12-02 16:54:02.520383

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8896e4853365'
down_revision: Union[str, None] = 'aa41b3449d79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'violations',
        sa.Column('closed_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('violations', 'closed_at')
