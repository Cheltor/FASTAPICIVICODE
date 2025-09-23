"""Add user_id column to observations

Revision ID: 117fb91af1ca
Revises: 
Create Date: 2024-10-15 19:27:29.360851

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '117fb91af1ca'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    """Return True if the given column exists on the given table."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column_name in [c["name"] for c in insp.get_columns(table_name)]

def _insp():
    return sa.inspect(op.get_bind())

def _has_table(table_name: str) -> bool:
    insp = _insp()
    return table_name in insp.get_table_names()

def _has_index(table_name: str, index_name: str) -> bool:
    insp = _insp()
    try:
        indexes = insp.get_indexes(table_name)
    except Exception:
        return False
    return any(ix.get("name") == index_name for ix in indexes)

def _has_unique_constraint(table_name: str, columns: list[str] | None = None, name: str | None = None) -> bool:
    insp = _insp()
    try:
        uniques = insp.get_unique_constraints(table_name)
    except Exception:
        return False
    for uc in uniques:
        if name and uc.get("name") == name:
            return True
        if columns and sorted(uc.get("column_names", [])) == sorted(columns):
            return True
    return False

def _get_unique_constraint_name(table_name: str, columns: list[str]) -> str | None:
    insp = _insp()
    try:
        uniques = insp.get_unique_constraints(table_name)
    except Exception:
        return None
    for uc in uniques:
        if sorted(uc.get("column_names", [])) == sorted(columns):
            return uc.get("name")
    return None

def _has_fk(table_name: str, *, name: str | None = None, constrained_columns: list[str] | None = None, referred_table: str | None = None, referred_columns: list[str] | None = None) -> bool:
    insp = _insp()
    try:
        fks = insp.get_foreign_keys(table_name)
    except Exception:
        return False
    for fk in fks:
        if name and fk.get("name") == name:
            return True
        ok = True
        if constrained_columns and sorted(fk.get("constrained_columns", [])) != sorted(constrained_columns):
            ok = False
        if referred_table and fk.get("referred_table") != referred_table:
            ok = False
        if referred_columns and sorted(fk.get("referred_columns", [])) != sorted(referred_columns):
            ok = False
        if ok and (constrained_columns or referred_table or referred_columns):
            return True
    return False

def drop_table_if_exists(table_name: str):
    if _has_table(table_name):
        op.drop_table(table_name)

def drop_index_if_exists(index_name: str, table_name: str):
    if _has_table(table_name) and _has_index(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)

def create_index_if_missing(index_name: str, table_name: str, columns: list[str], unique: bool = False):
    if _has_table(table_name) and not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=unique)

def add_column_if_missing(table_name: str, column: sa.Column):
    if _has_table(table_name) and not _has_column(table_name, column.name):
        op.add_column(table_name, column)

def drop_column_if_exists(table_name: str, column_name: str):
    if _has_table(table_name) and _has_column(table_name, column_name):
        op.drop_column(table_name, column_name)

def alter_column_nullable_if_exists(table_name: str, column_name: str, nullable: bool, existing_type: sa.types.TypeEngine | None = None, type_: sa.types.TypeEngine | None = None):
    if _has_table(table_name) and _has_column(table_name, column_name):
        kwargs = {"nullable": nullable}
        if existing_type is not None:
            kwargs["existing_type"] = existing_type
        if type_ is not None:
            kwargs["type_"] = type_
        op.alter_column(table_name, column_name, **kwargs)

def drop_unique_if_exists(table_name: str, columns: list[str] | None = None, name: str | None = None):
    if _has_table(table_name) and _has_unique_constraint(table_name, columns=columns, name=name):
        cname = name or _get_unique_constraint_name(table_name, columns or [])
        if cname:
            op.drop_constraint(cname, table_name, type_='unique')

def create_unique_if_missing(table_name: str, columns: list[str]):
    if _has_table(table_name) and not _has_unique_constraint(table_name, columns=columns):
        op.create_unique_constraint(None, table_name, columns)

def drop_fk_if_exists(table_name: str, name: str):
    if _has_table(table_name) and _has_fk(table_name, name=name):
        op.drop_constraint(name, table_name, type_='foreignkey')

def create_fk_if_missing(table_name: str, referred_table: str, local_cols: list[str], remote_cols: list[str]):
    if _has_table(table_name) and not _has_fk(table_name, constrained_columns=local_cols, referred_table=referred_table, referred_columns=remote_cols):
        op.create_foreign_key(None, table_name, referred_table, local_cols, remote_cols)


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    drop_table_if_exists('permits')
    drop_table_if_exists('schema_migrations')
    drop_table_if_exists('ar_internal_metadata')
    drop_index_if_exists('index_active_storage_attachments_on_blob_id', 'active_storage_attachments')
    drop_index_if_exists('index_active_storage_attachments_uniqueness', 'active_storage_attachments')
    create_index_if_missing(op.f('ix_active_storage_attachments_id'), 'active_storage_attachments', ['id'])
    drop_fk_if_exists('active_storage_attachments', 'fk_rails_c3b3935057')
    add_column_if_missing('active_storage_blobs', sa.Column('meta_data', sa.Text(), nullable=True))
    drop_index_if_exists('index_active_storage_blobs_on_key', 'active_storage_blobs')
    create_index_if_missing(op.f('ix_active_storage_blobs_id'), 'active_storage_blobs', ['id'])
    create_unique_if_missing('active_storage_blobs', ['key'])
    drop_column_if_exists('active_storage_blobs', 'metadata')
    drop_index_if_exists('index_active_storage_variant_records_uniqueness', 'active_storage_variant_records')
    create_index_if_missing(op.f('ix_active_storage_variant_records_id'), 'active_storage_variant_records', ['id'])
    drop_index_if_exists('index_address_contacts_on_address_id', 'address_contacts')
    drop_index_if_exists('index_address_contacts_on_contact_id', 'address_contacts')
    create_index_if_missing(op.f('ix_address_contacts_id'), 'address_contacts', ['id'])
    drop_index_if_exists('index_addresses_on_combadd', 'addresses')
    drop_index_if_exists('index_addresses_on_property_name', 'addresses')
    create_index_if_missing(op.f('ix_addresses_combadd'), 'addresses', ['combadd'])
    create_index_if_missing(op.f('ix_addresses_id'), 'addresses', ['id'])
    create_index_if_missing(op.f('ix_addresses_property_name'), 'addresses', ['property_name'])
    drop_index_if_exists('index_area_codes_on_area_id', 'area_codes')
    drop_index_if_exists('index_area_codes_on_code_id', 'area_codes')
    create_index_if_missing(op.f('ix_area_codes_id'), 'area_codes', ['id'])
    drop_index_if_exists('index_areas_on_inspection_id', 'areas')
    drop_index_if_exists('index_areas_on_unit_id', 'areas')
    create_index_if_missing(op.f('ix_areas_id'), 'areas', ['id'])
    # Drop only if the column exists (tolerant on partially migrated DBs)
    drop_column_if_exists('areas', 'room_id')
    drop_index_if_exists('index_business_contacts_on_business_id', 'business_contacts')
    drop_index_if_exists('index_business_contacts_on_contact_id', 'business_contacts')
    create_index_if_missing(op.f('ix_business_contacts_id'), 'business_contacts', ['id'])
    drop_index_if_exists('index_businesses_on_address_id', 'businesses')
    drop_index_if_exists('index_businesses_on_unit_id', 'businesses')
    create_index_if_missing(op.f('ix_businesses_id'), 'businesses', ['id'])
    drop_index_if_exists('index_citation_comments_on_citation_id', 'citation_comments')
    drop_index_if_exists('index_citation_comments_on_user_id', 'citation_comments')
    create_index_if_missing(op.f('ix_citation_comments_id'), 'citation_comments', ['id'])
    drop_index_if_exists('index_citations_on_code_id', 'citations')
    drop_index_if_exists('index_citations_on_unit_id', 'citations')
    drop_index_if_exists('index_citations_on_user_id', 'citations')
    drop_index_if_exists('index_citations_on_violation_id', 'citations')
    create_index_if_missing(op.f('ix_citations_id'), 'citations', ['id'])
    create_fk_if_missing('citations_codes', 'codes', ['code_id'], ['id'])
    create_fk_if_missing('citations_codes', 'citations', ['citation_id'], ['id'])
    create_index_if_missing(op.f('ix_codes_id'), 'codes', ['id'])
    alter_column_nullable_if_exists('comments', 'content', False, existing_type=sa.TEXT())
    drop_index_if_exists('index_comments_on_address_id', 'comments')
    drop_index_if_exists('index_comments_on_unit_id', 'comments')
    drop_index_if_exists('index_comments_on_user_id', 'comments')
    create_index_if_missing(op.f('ix_comments_id'), 'comments', ['id'])
    drop_index_if_exists('index_concerns_on_address_id', 'concerns')
    create_index_if_missing(op.f('ix_concerns_id'), 'concerns', ['id'])
    alter_column_nullable_if_exists('contact_comments', 'comment', False, existing_type=sa.TEXT())
    drop_index_if_exists('index_contact_comments_on_contact_id', 'contact_comments')
    drop_index_if_exists('index_contact_comments_on_user_id', 'contact_comments')
    create_index_if_missing(op.f('ix_contact_comments_id'), 'contact_comments', ['id'])
    create_index_if_missing(op.f('ix_contacts_id'), 'contacts', ['id'])
    drop_index_if_exists('index_inspection_codes_on_code_id', 'inspection_codes')
    drop_index_if_exists('index_inspection_codes_on_inspection_id', 'inspection_codes')
    create_index_if_missing(op.f('ix_inspection_codes_id'), 'inspection_codes', ['id'])
    drop_index_if_exists('index_inspection_comments_on_inspection_id', 'inspection_comments')
    drop_index_if_exists('index_inspection_comments_on_user_id', 'inspection_comments')
    create_index_if_missing(op.f('ix_inspection_comments_id'), 'inspection_comments', ['id'])
    drop_index_if_exists('index_inspections_on_address_id', 'inspections')
    drop_index_if_exists('index_inspections_on_business_id', 'inspections')
    drop_index_if_exists('index_inspections_on_contact_id', 'inspections')
    drop_index_if_exists('index_inspections_on_inspector_id', 'inspections')
    drop_index_if_exists('index_inspections_on_unit_id', 'inspections')
    create_index_if_missing(op.f('ix_inspections_id'), 'inspections', ['id'])
    drop_index_if_exists('index_licenses_on_business_id', 'licenses')
    drop_index_if_exists('index_licenses_on_inspection_id', 'licenses')
    create_index_if_missing(op.f('ix_licenses_id'), 'licenses', ['id'])
    drop_index_if_exists('index_notifications_on_inspection_id', 'notifications')
    drop_index_if_exists('index_notifications_on_user_id', 'notifications')
    create_index_if_missing(op.f('ix_notifications_id'), 'notifications', ['id'])
    # Add the column as nullable first
    add_column_if_missing('observations', sa.Column('user_id', sa.BigInteger(), nullable=True))

    # Set the user_id to 1 for all existing records
    if _has_table('observations') and _has_column('observations', 'user_id'):
        op.execute("UPDATE observations SET user_id = 1 WHERE user_id IS NULL")

    # Alter the column to make it NOT NULL after populating existing records
    if _has_table('observations') and _has_column('observations', 'user_id'):
        op.alter_column('observations', 'user_id', nullable=False)
    drop_index_if_exists('index_observations_on_area_id', 'observations')
    create_index_if_missing(op.f('ix_observations_id'), 'observations', ['id'])
    create_fk_if_missing('observations', 'users', ['user_id'], ['id'])
    drop_index_if_exists('index_prompts_on_room_id', 'prompts')
    create_index_if_missing(op.f('ix_prompts_id'), 'prompts', ['id'])
    create_index_if_missing(op.f('ix_rooms_id'), 'rooms', ['id'])
    drop_index_if_exists('index_unit_contacts_on_contact_id', 'unit_contacts')
    drop_index_if_exists('index_unit_contacts_on_unit_id', 'unit_contacts')
    create_index_if_missing(op.f('ix_unit_contacts_id'), 'unit_contacts', ['id'])
    drop_index_if_exists('index_units_on_address_id', 'units')
    create_index_if_missing(op.f('ix_units_id'), 'units', ['id'])
    drop_index_if_exists('index_users_on_email', 'users')
    drop_index_if_exists('index_users_on_reset_password_token', 'users')
    drop_index_if_exists('index_users_on_uid_and_provider', 'users')
    create_index_if_missing(op.f('ix_users_id'), 'users', ['id'])
    create_unique_if_missing('users', ['reset_password_token'])
    create_unique_if_missing('users', ['email'])
    drop_column_if_exists('users', 'uid')
    drop_column_if_exists('users', 'tokens')
    drop_column_if_exists('users', 'provider')
    drop_index_if_exists('index_versions_on_item_type_and_item_id', 'versions')
    create_index_if_missing(op.f('ix_versions_id'), 'versions', ['id'])
    drop_index_if_exists('index_violation_codes_on_code_id', 'violation_codes')
    drop_index_if_exists('index_violation_codes_on_violation_id', 'violation_codes')
    create_index_if_missing(op.f('ix_violation_codes_id'), 'violation_codes', ['id'])
    drop_index_if_exists('index_violation_comments_on_user_id', 'violation_comments')
    drop_index_if_exists('index_violation_comments_on_violation_id', 'violation_comments')
    create_index_if_missing(op.f('ix_violation_comments_id'), 'violation_comments', ['id'])
    op.alter_column('violations', 'business_id',
               existing_type=sa.INTEGER(),
               type_=sa.BigInteger(),
               existing_nullable=True)
    drop_index_if_exists('index_violations_on_address_id', 'violations')
    drop_index_if_exists('index_violations_on_inspection_id', 'violations')
    drop_index_if_exists('index_violations_on_unit_id', 'violations')
    drop_index_if_exists('index_violations_on_user_id', 'violations')
    create_index_if_missing(op.f('ix_violations_id'), 'violations', ['id'])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_violations_id'), table_name='violations')
    op.create_index('index_violations_on_user_id', 'violations', ['user_id'], unique=False)
    op.create_index('index_violations_on_unit_id', 'violations', ['unit_id'], unique=False)
    op.create_index('index_violations_on_inspection_id', 'violations', ['inspection_id'], unique=False)
    op.create_index('index_violations_on_address_id', 'violations', ['address_id'], unique=False)
    op.alter_column('violations', 'business_id',
               existing_type=sa.BigInteger(),
               type_=sa.INTEGER(),
               existing_nullable=True)
    op.drop_index(op.f('ix_violation_comments_id'), table_name='violation_comments')
    op.create_index('index_violation_comments_on_violation_id', 'violation_comments', ['violation_id'], unique=False)
    op.create_index('index_violation_comments_on_user_id', 'violation_comments', ['user_id'], unique=False)
    op.drop_index(op.f('ix_violation_codes_id'), table_name='violation_codes')
    op.create_index('index_violation_codes_on_violation_id', 'violation_codes', ['violation_id'], unique=False)
    op.create_index('index_violation_codes_on_code_id', 'violation_codes', ['code_id'], unique=False)
    op.drop_index(op.f('ix_versions_id'), table_name='versions')
    op.create_index('index_versions_on_item_type_and_item_id', 'versions', ['item_type', 'item_id'], unique=False)
    op.add_column('users', sa.Column('provider', sa.VARCHAR(), server_default=sa.text("'email'::character varying"), autoincrement=False, nullable=False))
    op.add_column('users', sa.Column('tokens', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True))
    op.add_column('users', sa.Column('uid', sa.VARCHAR(), server_default=sa.text("''::character varying"), autoincrement=False, nullable=False))
    op.drop_constraint(None, 'users', type_='unique')
    op.drop_constraint(None, 'users', type_='unique')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.create_index('index_users_on_uid_and_provider', 'users', ['uid', 'provider'], unique=True)
    op.create_index('index_users_on_reset_password_token', 'users', ['reset_password_token'], unique=True)
    op.create_index('index_users_on_email', 'users', ['email'], unique=True)
    op.drop_index(op.f('ix_units_id'), table_name='units')
    op.create_index('index_units_on_address_id', 'units', ['address_id'], unique=False)
    op.drop_index(op.f('ix_unit_contacts_id'), table_name='unit_contacts')
    op.create_index('index_unit_contacts_on_unit_id', 'unit_contacts', ['unit_id'], unique=False)
    op.create_index('index_unit_contacts_on_contact_id', 'unit_contacts', ['contact_id'], unique=False)
    op.drop_index(op.f('ix_rooms_id'), table_name='rooms')
    op.drop_index(op.f('ix_prompts_id'), table_name='prompts')
    op.create_index('index_prompts_on_room_id', 'prompts', ['room_id'], unique=False)
    op.drop_constraint(None, 'observations', type_='foreignkey')
    op.drop_index(op.f('ix_observations_id'), table_name='observations')
    op.create_index('index_observations_on_area_id', 'observations', ['area_id'], unique=False)
    op.drop_column('observations', 'user_id')
    op.drop_index(op.f('ix_notifications_id'), table_name='notifications')
    op.create_index('index_notifications_on_user_id', 'notifications', ['user_id'], unique=False)
    op.create_index('index_notifications_on_inspection_id', 'notifications', ['inspection_id'], unique=False)
    op.drop_index(op.f('ix_licenses_id'), table_name='licenses')
    op.create_index('index_licenses_on_inspection_id', 'licenses', ['inspection_id'], unique=False)
    op.create_index('index_licenses_on_business_id', 'licenses', ['business_id'], unique=False)
    op.drop_index(op.f('ix_inspections_id'), table_name='inspections')
    op.create_index('index_inspections_on_unit_id', 'inspections', ['unit_id'], unique=False)
    op.create_index('index_inspections_on_inspector_id', 'inspections', ['inspector_id'], unique=False)
    op.create_index('index_inspections_on_contact_id', 'inspections', ['contact_id'], unique=False)
    op.create_index('index_inspections_on_business_id', 'inspections', ['business_id'], unique=False)
    op.create_index('index_inspections_on_address_id', 'inspections', ['address_id'], unique=False)
    op.drop_index(op.f('ix_inspection_comments_id'), table_name='inspection_comments')
    op.create_index('index_inspection_comments_on_user_id', 'inspection_comments', ['user_id'], unique=False)
    op.create_index('index_inspection_comments_on_inspection_id', 'inspection_comments', ['inspection_id'], unique=False)
    op.drop_index(op.f('ix_inspection_codes_id'), table_name='inspection_codes')
    op.create_index('index_inspection_codes_on_inspection_id', 'inspection_codes', ['inspection_id'], unique=False)
    op.create_index('index_inspection_codes_on_code_id', 'inspection_codes', ['code_id'], unique=False)
    op.drop_index(op.f('ix_contacts_id'), table_name='contacts')
    op.drop_index(op.f('ix_contact_comments_id'), table_name='contact_comments')
    op.create_index('index_contact_comments_on_user_id', 'contact_comments', ['user_id'], unique=False)
    op.create_index('index_contact_comments_on_contact_id', 'contact_comments', ['contact_id'], unique=False)
    op.alter_column('contact_comments', 'comment',
               existing_type=sa.TEXT(),
               nullable=True)
    op.drop_index(op.f('ix_concerns_id'), table_name='concerns')
    op.create_index('index_concerns_on_address_id', 'concerns', ['address_id'], unique=False)
    op.drop_index(op.f('ix_comments_id'), table_name='comments')
    op.create_index('index_comments_on_user_id', 'comments', ['user_id'], unique=False)
    op.create_index('index_comments_on_unit_id', 'comments', ['unit_id'], unique=False)
    op.create_index('index_comments_on_address_id', 'comments', ['address_id'], unique=False)
    op.alter_column('comments', 'content',
               existing_type=sa.TEXT(),
               nullable=True)
    op.drop_index(op.f('ix_codes_id'), table_name='codes')
    op.drop_constraint(None, 'citations_codes', type_='foreignkey')
    op.drop_constraint(None, 'citations_codes', type_='foreignkey')
    op.drop_index(op.f('ix_citations_id'), table_name='citations')
    op.create_index('index_citations_on_violation_id', 'citations', ['violation_id'], unique=False)
    op.create_index('index_citations_on_user_id', 'citations', ['user_id'], unique=False)
    op.create_index('index_citations_on_unit_id', 'citations', ['unit_id'], unique=False)
    op.create_index('index_citations_on_code_id', 'citations', ['code_id'], unique=False)
    op.drop_index(op.f('ix_citation_comments_id'), table_name='citation_comments')
    op.create_index('index_citation_comments_on_user_id', 'citation_comments', ['user_id'], unique=False)
    op.create_index('index_citation_comments_on_citation_id', 'citation_comments', ['citation_id'], unique=False)
    op.drop_index(op.f('ix_businesses_id'), table_name='businesses')
    op.create_index('index_businesses_on_unit_id', 'businesses', ['unit_id'], unique=False)
    op.create_index('index_businesses_on_address_id', 'businesses', ['address_id'], unique=False)
    op.drop_index(op.f('ix_business_contacts_id'), table_name='business_contacts')
    op.create_index('index_business_contacts_on_contact_id', 'business_contacts', ['contact_id'], unique=False)
    op.create_index('index_business_contacts_on_business_id', 'business_contacts', ['business_id'], unique=False)
    # Recreate only if missing
    if not _has_column('areas', 'room_id'):
        op.add_column('areas', sa.Column('room_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.drop_index(op.f('ix_areas_id'), table_name='areas')
    op.create_index('index_areas_on_unit_id', 'areas', ['unit_id'], unique=False)
    op.create_index('index_areas_on_inspection_id', 'areas', ['inspection_id'], unique=False)
    op.drop_index(op.f('ix_area_codes_id'), table_name='area_codes')
    op.create_index('index_area_codes_on_code_id', 'area_codes', ['code_id'], unique=False)
    op.create_index('index_area_codes_on_area_id', 'area_codes', ['area_id'], unique=False)
    op.drop_index(op.f('ix_addresses_property_name'), table_name='addresses')
    op.drop_index(op.f('ix_addresses_id'), table_name='addresses')
    op.drop_index(op.f('ix_addresses_combadd'), table_name='addresses')
    op.create_index('index_addresses_on_property_name', 'addresses', ['property_name'], unique=False)
    op.create_index('index_addresses_on_combadd', 'addresses', ['combadd'], unique=False)
    op.drop_index(op.f('ix_address_contacts_id'), table_name='address_contacts')
    op.create_index('index_address_contacts_on_contact_id', 'address_contacts', ['contact_id'], unique=False)
    op.create_index('index_address_contacts_on_address_id', 'address_contacts', ['address_id'], unique=False)
    op.drop_index(op.f('ix_active_storage_variant_records_id'), table_name='active_storage_variant_records')
    op.create_index('index_active_storage_variant_records_uniqueness', 'active_storage_variant_records', ['blob_id', 'variation_digest'], unique=True)
    op.add_column('active_storage_blobs', sa.Column('metadata', sa.TEXT(), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'active_storage_blobs', type_='unique')
    op.drop_index(op.f('ix_active_storage_blobs_id'), table_name='active_storage_blobs')
    op.create_index('index_active_storage_blobs_on_key', 'active_storage_blobs', ['key'], unique=True)
    op.drop_column('active_storage_blobs', 'meta_data')
    op.create_foreign_key('fk_rails_c3b3935057', 'active_storage_attachments', 'active_storage_blobs', ['blob_id'], ['id'])
    op.drop_index(op.f('ix_active_storage_attachments_id'), table_name='active_storage_attachments')
    op.create_index('index_active_storage_attachments_uniqueness', 'active_storage_attachments', ['record_type', 'record_id', 'name', 'blob_id'], unique=True)
    op.create_index('index_active_storage_attachments_on_blob_id', 'active_storage_attachments', ['blob_id'], unique=False)
    op.create_table('ar_internal_metadata',
    sa.Column('key', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('value', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(precision=6), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(precision=6), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('key', name='ar_internal_metadata_pkey')
    )
    op.create_table('schema_migrations',
    sa.Column('version', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('version', name='schema_migrations_pkey')
    )
    op.create_table('permits',
    sa.Column('id', sa.BIGINT(), autoincrement=True, nullable=False),
    sa.Column('address_id', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('inspection_id', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('sent', sa.BOOLEAN(), autoincrement=False, nullable=True),
    sa.Column('revoked', sa.BOOLEAN(), autoincrement=False, nullable=True),
    sa.Column('fiscal_year', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('expiration_date', sa.DATE(), autoincrement=False, nullable=True),
    sa.Column('permitnumber', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('date_issued', sa.DATE(), autoincrement=False, nullable=True),
    sa.Column('conditions', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('paid', sa.BOOLEAN(), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(precision=6), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(precision=6), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id', name='permits_pkey')
    )
    # ### end Alembic commands ###
