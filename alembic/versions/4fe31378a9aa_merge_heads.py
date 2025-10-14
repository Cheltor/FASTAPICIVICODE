"""merge heads

Revision ID: 4fe31378a9aa
Revises: c1a2b3d4e5f6, g1_add_chat_logs_table
Create Date: 2025-10-13 20:37:22.463850

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4fe31378a9aa'
down_revision: Union[str, None] = ('c1a2b3d4e5f6', 'g1_add_chat_logs_table')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
