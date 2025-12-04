"""Add vacant_registrations table for annual vacant property tracking

Revision ID: f2d6c7b8a9e0
Revises: 9b3b4a7c9c7d
Create Date: 2025-12-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "f2d6c7b8a9e0"
down_revision: Union[str, None] = "9b3b4a7c9c7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "vacant_registrations" not in inspector.get_table_names():
        op.create_table(
            "vacant_registrations",
            sa.Column("id", sa.BigInteger(), primary_key=True, index=True),
            sa.Column("address_id", sa.BigInteger(), sa.ForeignKey("addresses.id"), nullable=False),
            sa.Column("registration_year", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("fee_amount", sa.Float(), server_default="0"),
            sa.Column("fee_paid", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("fee_paid_at", sa.DateTime(), nullable=True),
            sa.Column("fire_damage", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("registered_on", sa.Date(), nullable=True),
            sa.Column("expires_on", sa.Date(), nullable=True),
            sa.Column("maintenance_status", sa.String(), nullable=True),
            sa.Column("maintenance_notes", sa.Text(), nullable=True),
            sa.Column("security_status", sa.String(), nullable=True),
            sa.Column("security_notes", sa.Text(), nullable=True),
            sa.Column("compliance_checked_at", sa.DateTime(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("address_id", "registration_year", name="uq_vacant_registrations_address_year"),
        )

    inspector = inspect(bind)
    existing_indexes = (
        {idx["name"] for idx in inspector.get_indexes("vacant_registrations")}
        if "vacant_registrations" in inspector.get_table_names()
        else set()
    )
    if "ix_vacant_registrations_address_id" not in existing_indexes:
        op.create_index(
            op.f("ix_vacant_registrations_address_id"),
            "vacant_registrations",
            ["address_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "vacant_registrations" in inspector.get_table_names():
        op.drop_index(op.f("ix_vacant_registrations_address_id"), table_name="vacant_registrations")
        op.drop_table("vacant_registrations")
