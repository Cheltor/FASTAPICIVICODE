"""Add observation_codes join table

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2025-08-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str, schema: str | None = None) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        return insp.has_table(table_name, schema=schema)
    except TypeError:
        return insp.has_table(table_name, schema)


def upgrade() -> None:
    # Create the observation_codes join table if missing
    if not _has_table('observation_codes'):
        op.create_table(
            'observation_codes',
            sa.Column('observation_id', sa.BigInteger(), sa.ForeignKey('observations.id'), primary_key=True, nullable=False),
            sa.Column('code_id', sa.BigInteger(), sa.ForeignKey('codes.id'), primary_key=True, nullable=False),
        )


def downgrade() -> None:
    # Drop the observation_codes join table if present
    if _has_table('observation_codes'):
        op.drop_table('observation_codes')
