"""Add license_type to document_templates

Revision ID: 9b3b4a7c9c7d
Revises: 8896e4853365
Create Date: 2025-12-02 22:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "9b3b4a7c9c7d"
down_revision: Union[str, None] = "8896e4853365"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    cols = {col["name"] for col in inspector.get_columns("document_templates")} \
        if "document_templates" in inspector.get_table_names() else set()
    if "license_type" not in cols:
        op.add_column("document_templates", sa.Column("license_type", sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = {col["name"] for col in inspector.get_columns("document_templates")} \
        if "document_templates" in inspector.get_table_names() else set()
    if "license_type" in cols:
        op.drop_column("document_templates", "license_type")
