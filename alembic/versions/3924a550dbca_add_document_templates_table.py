"""Add document_templates table

Revision ID: 3924a550dbca
Revises: 54832fde3607
Create Date: 2025-11-30 22:20:37.870085

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '3924a550dbca'
down_revision: Union[str, None] = '54832fde3607'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if 'document_templates' not in inspector.get_table_names():
        op.create_table(
            'document_templates',
            sa.Column('id', sa.BigInteger(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('category', sa.String(), nullable=False),
            sa.Column('filename', sa.String(), nullable=False),
            sa.Column('content', sa.LargeBinary(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )


def downgrade() -> None:
    op.drop_table('document_templates')
