"""Add cases and case_comments tables

Revision ID: j1a2b3c4d5e6
Revises: i9a8b7c6d5e4
Create Date: 2024-03-12 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'j1a2b3c4d5e6'
down_revision = 'i9a8b7c6d5e4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'cases',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('case_number', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('address_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['address_id'], ['addresses.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('case_number')
    )
    op.create_table(
        'case_comments',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('case_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('attachments', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('case_comments')
    op.drop_table('cases')
