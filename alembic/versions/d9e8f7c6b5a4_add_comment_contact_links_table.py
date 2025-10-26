"""Add comment_contact_links table

Revision ID: d9e8f7c6b5a4
Revises: b1e2c3d4f5a6
Create Date: 2025-10-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd9e8f7c6b5a4'
down_revision: Union[str, None] = 'i9a8b7c6d5e4'
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
    # Create comment_contact_links table if it doesn't exist
    if not _has_table('comment_contact_links'):
        op.create_table(
            'comment_contact_links',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column('comment_id', sa.BigInteger(), sa.ForeignKey('comments.id', ondelete='CASCADE'), nullable=False),
            sa.Column('contact_id', sa.BigInteger(), sa.ForeignKey('contacts.id', ondelete='CASCADE'), nullable=False),
            sa.Column('actor_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('created_at', postgresql.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', postgresql.TIMESTAMP(timezone=False), nullable=False, server_default=sa.text('now()')),
        )
        # Create helpful indexes (safe - wrapped in try/except)
        try:
            op.create_index(op.f('ix_comment_contact_links_id'), 'comment_contact_links', ['id'])
            op.create_index(op.f('ix_comment_contact_links_comment_id'), 'comment_contact_links', ['comment_id'])
            op.create_index(op.f('ix_comment_contact_links_contact_id'), 'comment_contact_links', ['contact_id'])
        except Exception:
            pass


def downgrade() -> None:
    # Drop table if exists
    if _has_table('comment_contact_links'):
        op.drop_table('comment_contact_links')
