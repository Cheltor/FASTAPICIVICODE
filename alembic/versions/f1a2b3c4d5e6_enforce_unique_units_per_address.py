"""
Enforce unique unit numbers per address by normalizing and adding a unique index.

Revision ID: f1a2b3c4d5e6
Revises: bc1efe6b5407
Create Date: 2025-08-26
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = 'bc1efe6b5407'
branch_labels = None
depends_on = None

def upgrade():
    # Normalize existing numbers to TRIM + UPPER so index can enforce uniqueness
    op.execute("UPDATE units SET number = UPPER(TRIM(number)) WHERE number IS NOT NULL;")
    # Compute survivors and duplicates
    op.execute(
        """
        WITH survivors AS (
            SELECT address_id, number, MIN(id) AS keep_id
            FROM units
            GROUP BY address_id, number
        ),
        dups AS (
            SELECT u.id AS dup_id, s.keep_id
            FROM units u
            JOIN survivors s
              ON u.address_id = s.address_id AND u.number = s.number
            WHERE u.id <> s.keep_id
        )
        -- Remap foreign keys in dependent tables
        , upd_comments AS (
            UPDATE comments c SET unit_id = d.keep_id
            FROM dups d
            WHERE c.unit_id = d.dup_id
            RETURNING 1
        )
        , upd_areas AS (
            UPDATE areas a SET unit_id = d.keep_id
            FROM dups d
            WHERE a.unit_id = d.dup_id
            RETURNING 1
        )
        , upd_businesses AS (
            UPDATE businesses b SET unit_id = d.keep_id
            FROM dups d
            WHERE b.unit_id = d.dup_id
            RETURNING 1
        )
        , upd_citations AS (
            UPDATE citations c SET unit_id = d.keep_id
            FROM dups d
            WHERE c.unit_id = d.dup_id
            RETURNING 1
        )
        , upd_violations AS (
            UPDATE violations v SET unit_id = d.keep_id
            FROM dups d
            WHERE v.unit_id = d.dup_id
            RETURNING 1
        )
        , upd_inspections AS (
            UPDATE inspections i SET unit_id = d.keep_id
            FROM dups d
            WHERE i.unit_id = d.dup_id
            RETURNING 1
        )
        , upd_unit_contacts AS (
            UPDATE unit_contacts uc SET unit_id = d.keep_id
            FROM dups d
            WHERE uc.unit_id = d.dup_id
            RETURNING 1
        )
        -- Finally, delete duplicate unit rows
        DELETE FROM units u USING dups d WHERE u.id = d.dup_id;
        """
    )
    # Create a unique index on (number, address_id) (idempotent)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_units_number_address ON units (number, address_id);")


def downgrade():
    # Drop the unique index
    insp = sa.inspect(op.get_bind())
    try:
        indexes = insp.get_indexes('units')
    except Exception:
        indexes = []
    if any(ix.get('name') == 'ux_units_number_address' for ix in indexes):
        op.drop_index('ux_units_number_address', table_name='units')
