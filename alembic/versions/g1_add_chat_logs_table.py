"""add chat_logs table

Revision ID: g1_add_chat_logs_table
Revises: e7c9a1b2c3d4
Create Date: 2025-10-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g1_add_chat_logs_table'
down_revision = 'e7c9a1b2c3d4'
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())
    if 'chat_logs' not in tables:
        op.create_table(
            'chat_logs',
            sa.Column('id', sa.BigInteger(), primary_key=True, index=True),
            sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('thread_id', sa.String(), nullable=True),
            sa.Column('user_message', sa.Text(), nullable=False),
            sa.Column('assistant_reply', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )


def downgrade():
    insp = sa.inspect(op.get_bind())
    tables = set()
    try:
        tables = set(insp.get_table_names())
    except Exception:
        pass
    if 'chat_logs' in tables:
        op.drop_table('chat_logs')
