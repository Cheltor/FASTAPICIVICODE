from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, BigInteger, Date, func
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# ActiveStorageAttachments
class ActiveStorageAttachment(Base):
    __tablename__ = "active_storage_attachments"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String, nullable=False)
    record_type = Column(String, nullable=False)
    record_id = Column(BigInteger, nullable=False)
    blob_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, nullable=False)

# ActiveStorageBlobs
class ActiveStorageBlob(Base):
    __tablename__ = "active_storage_blobs"

    id = Column(BigInteger, primary_key=True, index=True)
    key = Column(String, nullable=False, unique=True)
    filename = Column(String, nullable=False)
    content_type = Column(String)
    meta_data = Column(Text)
    service_name = Column(String, nullable=False)
    byte_size = Column(BigInteger, nullable=False)
    checksum = Column(String)
    created_at = Column(DateTime, nullable=False)

# ActiveStorageVariantRecords
class ActiveStorageVariantRecord(Base):
    __tablename__ = "active_storage_variant_records"

    id = Column(BigInteger, primary_key=True, index=True)
    blob_id = Column(BigInteger, ForeignKey('active_storage_blobs.id'), nullable=False)
    variation_digest = Column(String, nullable=False)

# Addresses
class Address(Base):
    __tablename__ = "addresses"

    id = Column(BigInteger, primary_key=True, index=True)
    pid = Column(String)
    ownername = Column(String)
    owneraddress = Column(String)
    ownercity = Column(String)
    ownerstate = Column(String)
    ownerzip = Column(String)
    streetnumb = Column(String)
    streetname = Column(String)
    streettype = Column(String)
    landusecode = Column(String)
    zoning = Column(String)
    owneroccupiedin = Column(String)
    vacant = Column(String)
    absent = Column(String)
    premisezip = Column(String)
    combadd = Column(String, index=True)
    outstanding = Column(Boolean, default=False)
    name = Column(String)
    proptype = Column(Integer, default=1)
    property_type = Column(String)
    property_name = Column(String, index=True)
    aka = Column(String)
    district = Column(String)
    property_id = Column(String)
    vacancy_status = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, onupdate=func.now(), server_default=func.now())

# AddressContacts
class AddressContact(Base):
    __tablename__ = "address_contacts"

    id = Column(BigInteger, primary_key=True, index=True)
    address_id = Column(BigInteger, ForeignKey('addresses.id'))
    contact_id = Column(BigInteger, ForeignKey('contacts.id'))
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# Areas
class Area(Base):
    __tablename__ = "areas"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String)
    notes = Column(Text)
    photos = Column(String)
    inspection_id = Column(BigInteger, ForeignKey('inspections.id'), nullable=False)
    floor = Column(Integer)
    unit_id = Column(BigInteger, ForeignKey('units.id'))
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# AreaCodes
class AreaCode(Base):
    __tablename__ = "area_codes"

    id = Column(BigInteger, primary_key=True, index=True)
    area_id = Column(BigInteger, ForeignKey('areas.id'), nullable=False)
    code_id = Column(BigInteger, ForeignKey('codes.id'), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# Businesses
class Business(Base):
    __tablename__ = "businesses"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String)
    address_id = Column(BigInteger, ForeignKey('addresses.id'), nullable=False)
    unit_id = Column(BigInteger, ForeignKey('units.id'))
    website = Column(String)
    email = Column(String)
    phone = Column(String)
    trading_as = Column(String)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# BusinessContacts
class BusinessContact(Base):
    __tablename__ = "business_contacts"

    id = Column(BigInteger, primary_key=True, index=True)
    business_id = Column(BigInteger, ForeignKey('businesses.id'), nullable=False)
    contact_id = Column(BigInteger, ForeignKey('contacts.id'), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# Citations
class Citation(Base):
    __tablename__ = "citations"

    id = Column(BigInteger, primary_key=True, index=True)
    fine = Column(Integer)
    deadline = Column(Date)
    violation_id = Column(BigInteger, ForeignKey('violations.id'), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    status = Column(Integer)
    trial_date = Column(Date)
    code_id = Column(BigInteger, ForeignKey('codes.id'), nullable=False)
    citationid = Column(String)
    unit_id = Column(BigInteger, ForeignKey('units.id'))

# CitationsCodes (join table for Many-to-Many relationships)
class CitationCode(Base):
    __tablename__ = "citations_codes"
    
    citation_id = Column(BigInteger, ForeignKey('citations.id'), primary_key=True, nullable=False)
    code_id = Column(BigInteger, ForeignKey('codes.id'), primary_key=True, nullable=False)


# CitationComments
class CitationComment(Base):
    __tablename__ = "citation_comments"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    citation_id = Column(BigInteger, ForeignKey('citations.id'), nullable=False)
    content = Column(Text)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# Codes
class Code(Base):
    __tablename__ = "codes"

    id = Column(BigInteger, primary_key=True, index=True)
    chapter = Column(String)
    section = Column(String)
    name = Column(String)
    description = Column(String)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# Comments
class Comment(Base):
    __tablename__ = "comments"
    
    id = Column(BigInteger, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    address_id = Column(BigInteger, ForeignKey('addresses.id'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    unit_id = Column(BigInteger, ForeignKey('units.id'))
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# Concerns
class Concern(Base):
    __tablename__ = "concerns"
    
    id = Column(BigInteger, primary_key=True, index=True)
    address_id = Column(BigInteger, ForeignKey('addresses.id'), nullable=False)
    content = Column(Text)
    emailorphone = Column(String)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# Contacts
class Contact(Base):
    __tablename__ = "contacts"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String)
    email = Column(String)
    phone = Column(String)
    notes = Column(Text, default="")
    hidden = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# ContactComments
class ContactComment(Base):
    __tablename__ = "contact_comments"
    
    id = Column(BigInteger, primary_key=True, index=True)
    comment = Column(Text)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    contact_id = Column(BigInteger, ForeignKey('contacts.id'), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


# Units
class Unit(Base):
    __tablename__ = "units"

    id = Column(BigInteger, primary_key=True, index=True)
    number = Column(String)
    address_id = Column(BigInteger, ForeignKey('addresses.id'), nullable=False)
    vacancy_status = Column(String)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# InspectionCodes
class InspectionCode(Base):
    __tablename__ = "inspection_codes"
    
    id = Column(BigInteger, primary_key=True, index=True)
    inspection_id = Column(BigInteger, ForeignKey('inspections.id'), nullable=False)
    code_id = Column(BigInteger, ForeignKey('codes.id'), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# InspectionComments
class InspectionComment(Base):
    __tablename__ = "inspection_comments"
    
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    inspection_id = Column(BigInteger, ForeignKey('inspections.id'), nullable=False)
    content = Column(Text)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# Inspections
class Inspection(Base):
    __tablename__ = "inspections"
    
    id = Column(BigInteger, primary_key=True, index=True)
    source = Column(String)
    status = Column(String)
    attachments = Column(String)
    result = Column(String)
    description = Column(Text)
    thoughts = Column(Text)
    originator = Column(String)
    unit_id = Column(BigInteger, ForeignKey('units.id'))
    address_id = Column(BigInteger, ForeignKey('addresses.id'), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    assignee = Column(String)
    inspector_id = Column(BigInteger, ForeignKey('users.id'))
    name = Column(String)
    email = Column(String)
    phone = Column(String)
    scheduled_datetime = Column(DateTime)
    photos = Column(String)
    notes_area_1 = Column(Text)
    notes_area_2 = Column(Text)
    notes_area_3 = Column(Text)
    intphotos = Column(String)
    extphotos = Column(String)
    contact_id = Column(BigInteger, ForeignKey('contacts.id'))
    new_contact_name = Column(String)
    new_contact_email = Column(String)
    new_contact_phone = Column(String)
    new_chapter = Column(String)
    new_section = Column(String)
    new_name = Column(String)
    new_description = Column(String)
    confirmed = Column(Boolean, default=False)
    business_id = Column(BigInteger, ForeignKey('businesses.id'))
    start_time = Column(DateTime)
    paid = Column(Boolean, default=False, nullable=False)

# Licenses
class License(Base):
    __tablename__ = "licenses"
    
    id = Column(BigInteger, primary_key=True, index=True)
    inspection_id = Column(BigInteger, ForeignKey('inspections.id'), nullable=False)
    sent = Column(Boolean)
    revoked = Column(Boolean)
    fiscal_year = Column(String)
    expiration_date = Column(Date)
    license_type = Column(Integer)
    business_id = Column(BigInteger, ForeignKey('businesses.id'))
    license_number = Column(String)
    date_issued = Column(Date)
    conditions = Column(Text)
    paid = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# Notifications
class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(BigInteger, primary_key=True, index=True)
    title = Column(String)
    body = Column(Text)
    inspection_id = Column(BigInteger, ForeignKey('inspections.id'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# Observations
class Observation(Base):
    __tablename__ = "observations"
    
    id = Column(BigInteger, primary_key=True, index=True)
    content = Column(Text)
    area_id = Column(BigInteger, ForeignKey('areas.id'), nullable=False)
    photos = Column(String)
    potentialvio = Column(Boolean)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# Prompts
class Prompt(Base):
    __tablename__ = "prompts"
    
    id = Column(BigInteger, primary_key=True, index=True)
    content = Column(String)
    room_id = Column(BigInteger, ForeignKey('rooms.id'), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# Rooms
class Room(Base):
    __tablename__ = "rooms"
    
    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# UnitContacts
class UnitContact(Base):
    __tablename__ = "unit_contacts"
    
    id = Column(BigInteger, primary_key=True, index=True)
    unit_id = Column(BigInteger, ForeignKey('units.id'), nullable=False)
    contact_id = Column(BigInteger, ForeignKey('contacts.id'), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# Users
class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)
    email = Column(String, nullable=False, unique=True, default="")
    encrypted_password = Column(String, nullable=False, default="")
    reset_password_token = Column(String, unique=True)
    reset_password_sent_at = Column(DateTime)
    remember_created_at = Column(DateTime)
    name = Column(String)
    phone = Column(String)
    role = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# Versions
class Version(Base):
    __tablename__ = "versions"
    
    id = Column(BigInteger, primary_key=True, index=True)
    item_type = Column(String, nullable=False)
    item_id = Column(BigInteger, nullable=False)
    event = Column(String, nullable=False)
    whodunnit = Column(String)
    object = Column(Text)
    created_at = Column(DateTime)

# ViolationCodes
class ViolationCode(Base):
    __tablename__ = "violation_codes"
    
    id = Column(BigInteger, primary_key=True, index=True)
    violation_id = Column(BigInteger, ForeignKey('violations.id'), nullable=False)
    code_id = Column(BigInteger, ForeignKey('codes.id'), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# ViolationComments
class ViolationComment(Base):
    __tablename__ = "violation_comments"
    
    id = Column(BigInteger, primary_key=True, index=True)
    violation_id = Column(BigInteger, ForeignKey('violations.id'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    content = Column(Text)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

# Violations
class Violation(Base):
    __tablename__ = "violations"
    
    id = Column(BigInteger, primary_key=True, index=True)
    description = Column(String)
    status = Column(Integer)
    address_id = Column(BigInteger, ForeignKey('addresses.id'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    deadline = Column(String)
    violation_type = Column(String)
    extend = Column(Integer, default=0)
    unit_id = Column(BigInteger, ForeignKey('units.id'))
    inspection_id = Column(BigInteger, ForeignKey('inspections.id'))
    comment = Column(Text)
    business_id = Column(BigInteger)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)