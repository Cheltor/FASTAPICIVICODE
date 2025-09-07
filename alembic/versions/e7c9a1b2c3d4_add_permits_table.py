"""add permits table

Revision ID: e7c9a1b2c3d4
Revises: f1a2b3c4d5e6
Create Date: 2025-09-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7c9a1b2c3d4'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'permits',
        sa.Column('id', sa.BigInteger(), primary_key=True, index=True),
        sa.Column('inspection_id', sa.BigInteger(), sa.ForeignKey('inspections.id'), nullable=False),
        sa.Column('permit_type', sa.String(), nullable=True),
        sa.Column('business_id', sa.BigInteger(), sa.ForeignKey('businesses.id'), nullable=True),
        sa.Column('permit_number', sa.String(), nullable=True),
        sa.Column('date_issued', sa.Date(), nullable=True),
        sa.Column('expiration_date', sa.Date(), nullable=True),
        sa.Column('conditions', sa.Text(), nullable=True),
        sa.Column('paid', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint('uq_permits_inspection_id', 'permits', ['inspection_id'])


def downgrade():
    op.drop_constraint('uq_permits_inspection_id', 'permits', type_='unique')
    op.drop_table('permits')
