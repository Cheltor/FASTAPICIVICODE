"""add app_settings table

Revision ID: c1a2b3d4e5f6
Revises: 
Create Date: 2025-10-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c1a2b3d4e5f6'
down_revision = 'fb1d50b069a7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(), primary_key=True, nullable=False),
        sa.Column('value', sa.String(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'app_settings_audit',
        sa.Column('id', sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('old_value', sa.String(), nullable=True),
        sa.Column('new_value', sa.String(), nullable=True),
        sa.Column('changed_by', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('changed_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table('app_settings_audit')
    op.drop_table('app_settings')
