"""Add case_id to inspections and violations

Revision ID: k1a2b3c4d5e6
Revises: j1a2b3c4d5e6
Create Date: 2024-03-12 10:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'k1a2b3c4d5e6'
down_revision = 'j1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('inspections', sa.Column('case_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key(None, 'inspections', 'cases', ['case_id'], ['id'])
    op.add_column('violations', sa.Column('case_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key(None, 'violations', 'cases', ['case_id'], ['id'])


def downgrade():
    op.drop_constraint(None, 'violations', type_='foreignkey')
    op.drop_column('violations', 'case_id')
    op.drop_constraint(None, 'inspections', type_='foreignkey')
    op.drop_column('inspections', 'case_id')
