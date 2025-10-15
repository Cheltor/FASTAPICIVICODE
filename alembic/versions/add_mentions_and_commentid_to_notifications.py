"""Add mentions table and add comment_id to notifications

Revision ID: b1e2c3d4f5a6
Revises: 
Create Date: 2025-10-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b1e2c3d4f5a6'
down_revision: Union[str, None] = '4fe31378a9aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return table_name in insp.get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column_name in [c['name'] for c in insp.get_columns(table_name)]


def upgrade() -> None:
    # Make notifications.inspection_id nullable if it exists
    if _has_table('notifications') and _has_column('notifications', 'inspection_id'):
        try:
            op.alter_column('notifications', 'inspection_id', nullable=True, existing_type=sa.BigInteger())
        except Exception:
            pass

    # Add comment_id to notifications if missing
    if _has_table('notifications') and not _has_column('notifications', 'comment_id'):
        op.add_column('notifications', sa.Column('comment_id', sa.BigInteger(), nullable=True))

    # Create mentions table
    if not _has_table('mentions'):
        op.create_table(
            'mentions',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column('comment_id', sa.BigInteger(), nullable=False),
            sa.Column('user_id', sa.BigInteger(), nullable=False),
            sa.Column('actor_id', sa.BigInteger(), nullable=True),
            sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('created_at', postgresql.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', postgresql.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text('now()')),
        )
        # Create simple indexes
        try:
            op.create_index(op.f('ix_mentions_id'), 'mentions', ['id'])
            op.create_index(op.f('ix_mentions_user_id'), 'mentions', ['user_id'])
            op.create_index(op.f('ix_mentions_comment_id'), 'mentions', ['comment_id'])
        except Exception:
            pass


def downgrade() -> None:
    # Drop mentions table
    if _has_table('mentions'):
        op.drop_table('mentions')

    # Drop comment_id column from notifications
    if _has_table('notifications') and _has_column('notifications', 'comment_id'):
        op.drop_column('notifications', 'comment_id')

    # Optionally make inspection_id not nullable again -- skip to be safe
    pass
