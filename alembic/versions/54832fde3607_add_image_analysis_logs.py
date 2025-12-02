"""add_image_analysis_logs

Revision ID: 54832fde3607
Revises: cedff70779f4
Create Date: 2025-11-21 16:26:46.710685

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '54832fde3607'
down_revision: Union[str, None] = 'cedff70779f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if 'image_analysis_logs' not in inspector.get_table_names():
        op.create_table(
            'image_analysis_logs',
            sa.Column('id', sa.BigInteger(), nullable=False),
            sa.Column('user_id', sa.BigInteger(), nullable=False),
            sa.Column('image_count', sa.Integer(), nullable=True),
            sa.Column('result', sa.Text(), nullable=True),
            sa.Column('status', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )

    existing_indexes = {idx['name'] for idx in inspector.get_indexes('image_analysis_logs')} if 'image_analysis_logs' in inspector.get_table_names() else set()
    if op.f('ix_image_analysis_logs_id') not in existing_indexes:
        op.create_index(op.f('ix_image_analysis_logs_id'), 'image_analysis_logs', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_image_analysis_logs_id'), table_name='image_analysis_logs')
    op.drop_table('image_analysis_logs')
