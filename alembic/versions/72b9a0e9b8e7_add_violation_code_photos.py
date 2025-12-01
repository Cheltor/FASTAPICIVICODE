"""Add table linking violation photos to specific codes

Revision ID: 72b9a0e9b8e7
Revises: 0a444448841e
Create Date: 2025-12-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '72b9a0e9b8e7'
down_revision: Union[str, None] = '0a444448841e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'violation_code_photos',
        sa.Column('id', sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column('violation_id', sa.BigInteger(), sa.ForeignKey('violations.id'), nullable=False),
        sa.Column('code_id', sa.BigInteger(), sa.ForeignKey('codes.id'), nullable=False),
        sa.Column('attachment_id', sa.BigInteger(), sa.ForeignKey('active_storage_attachments.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('violation_id', 'code_id', 'attachment_id', name='uq_violation_code_photos'),
    )
    op.create_index(op.f('ix_violation_code_photos_id'), 'violation_code_photos', ['id'], unique=False)
    op.create_index('ix_violation_code_photos_violation_id', 'violation_code_photos', ['violation_id'], unique=False)
    op.create_index('ix_violation_code_photos_attachment_id', 'violation_code_photos', ['attachment_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_violation_code_photos_attachment_id', table_name='violation_code_photos')
    op.drop_index('ix_violation_code_photos_violation_id', table_name='violation_code_photos')
    op.drop_index(op.f('ix_violation_code_photos_id'), table_name='violation_code_photos')
    op.drop_table('violation_code_photos')
