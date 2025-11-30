from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, BigInteger, Date, func, UniqueConstraint, text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timedelta
try:
    # If running normally (e.g., FastAPI server)
    from constants import DEADLINE_OPTIONS, DEADLINE_VALUES
except ImportError:
    # If running in Alembic context
    from .constants import DEADLINE_OPTIONS, DEADLINE_VALUES


Base = declarative_base()

# Small table for application-wide settings (key/value)
class AppSetting(Base):
    """
    Application-wide settings.

    Stores key-value pairs for global application configuration that can be
    modified at runtime.

    Attributes:
        key (str): The unique key for the setting.
        value (str): The value of the setting.
        updated_at (datetime): The timestamp when the setting was last updated.
    """
    __tablename__ = "app_settings"

    key = Column(String, primary_key=True, index=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


# Audit history for app settings
class AppSettingAudit(Base):
    """
    Audit log for application settings changes.

    Tracks changes made to `AppSetting` records for accountability.

    Attributes:
        id (int): The primary key.
        key (str): The key of the setting that changed.
        old_value (str): The previous value of the setting.
        new_value (str): The new value of the setting.
        changed_by (int): The ID of the user who made the change.
        changed_at (datetime): The timestamp when the change occurred.
        user (User): The user object who made the change.
    """
    __tablename__ = 'app_settings_audit'

    id = Column(BigInteger, primary_key=True, index=True)
    key = Column(String, nullable=False)
    old_value = Column(String)
    new_value = Column(String)
    changed_by = Column(BigInteger, ForeignKey('users.id'))
    changed_at = Column(DateTime, default=func.now(), nullable=False)

    user = relationship('User')


# Chat logs for assistant interactions
class ChatLog(Base):
    """
    Logs of interactions with the AI assistant.

    Attributes:
        id (int): The primary key.
        user_id (int): The ID of the user initiating the chat.
        thread_id (str): The thread ID used by the OpenAI Assistant API.
        user_message (str): The message sent by the user.
        assistant_reply (str): The reply received from the assistant.
        created_at (datetime): The timestamp of the interaction.
        user (User): The user object.
    """
    __tablename__ = 'chat_logs'

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    thread_id = Column(String, nullable=True, index=True)
    user_message = Column(Text, nullable=False)
    assistant_reply = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    user = relationship('User')

# Image Analysis Logs
class ImageAnalysisLog(Base):
    """
    Logs of image analysis operations.

    Tracks the results of automated image analysis tasks.

    Attributes:
        id (int): The primary key.
        user_id (int): The ID of the user who requested the analysis.
        image_count (int): The number of images analyzed.
        result (str): JSON string containing the analysis results.
        status (str): The status of the analysis job.
        created_at (datetime): The timestamp when the log was created.
        user (User): The user object.
    """
    __tablename__ = 'image_analysis_logs'

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    image_count = Column(Integer)
    result = Column(Text) # JSON string
    status = Column(String)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    user = relationship('User')

    # Relationship to attachments (polymorphic-like)
    # We will manually query ActiveStorageAttachment where record_type='ImageAnalysisLog' and record_id=this.id

# ActiveStorageAttachments
class ActiveStorageAttachment(Base):
    """
    Represents an attachment in Active Storage.

    Links a record (like an Inspection or Violation) to a Blob (the actual file).
    Modeled after Rails ActiveStorage.

    Attributes:
        id (int): The primary key.
        name (str): The name of the attachment.
        record_type (str): The type of the record being attached to (e.g., "Inspection").
        record_id (int): The ID of the record being attached to.
        blob_id (int): The ID of the associated blob.
        created_at (datetime): The creation timestamp.
    """
    __tablename__ = "active_storage_attachments"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String, nullable=False)
    record_type = Column(String, nullable=False)
    record_id = Column(BigInteger, nullable=False)
    blob_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, nullable=False)

# ActiveStorageBlobs
class ActiveStorageBlob(Base):
    """
    Represents a file blob in Active Storage.

    Stores metadata about the file, such as filename, content type, and storage key.

    Attributes:
        id (int): The primary key.
        key (str): The unique key used to retrieve the file from the storage service.
        filename (str): The original name of the file.
        content_type (str): The MIME type of the file.
        meta_data (str): Additional metadata (e.g., width, height).
        service_name (str): The name of the storage service (e.g., "azure").
        byte_size (int): The size of the file in bytes.
        checksum (str): The file checksum.
        created_at (datetime): The creation timestamp.
    """
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
    """
    Represents a variant of an Active Storage blob.

    Used for storing information about processed versions of files (e.g., resized images).

    Attributes:
        id (int): The primary key.
        blob_id (int): The ID of the original blob.
        variation_digest (str): A digest representing the variation parameters.
    """
    __tablename__ = "active_storage_variant_records"

    id = Column(BigInteger, primary_key=True, index=True)
    blob_id = Column(BigInteger, ForeignKey('active_storage_blobs.id'), nullable=False)
    variation_digest = Column(String, nullable=False)

# Addresses
class Address(Base):
    """
    Represents a physical address.

    Attributes:
        id (int): Primary key.
        pid (str): Property ID.
        ownername (str): Owner's name.
        owneraddress (str): Owner's address.
        ownercity (str): Owner's city.
        ownerstate (str): Owner's state.
        ownerzip (str): Owner's ZIP code.
        streetnumb (str): Street number.
        streetname (str): Street name.
        streettype (str): Street type.
        landusecode (str): Land use code.
        zoning (str): Zoning code.
        owneroccupiedin (str): Owner occupied indicator.
        vacant (str): Vacancy status.
        absent (str): Absentee owner indicator.
        premisezip (str): Premise ZIP code.
        combadd (str): Combined address string.
        outstanding (bool): Outstanding status.
        name (str): Name associated with the address.
        proptype (int): Property type code.
        property_type (str): Property type description.
        property_name (str): Property name.
        aka (str): Also known as.
        district (str): District name.
        property_id (str): Alternate property ID.
        vacancy_status (str): Current vacancy status.
        latitude (float): Latitude coordinate.
        longitude (float): Longitude coordinate.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        inspections (list[Inspection]): Related inspections.
        comments (list[Comment]): Related comments.
        violations (list[Violation]): Related violations.
        businesses (list[Business]): Related businesses.
        address_contacts (list[AddressContact]): Link table to contacts.
        contacts (list[Contact]): Related contacts.
    """
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

    # Relationships
    inspections = relationship("Inspection", back_populates="address")  # Address has many Inspections
    comments = relationship("Comment", back_populates="address", cascade="all, delete-orphan") # Address has many Comments
    violations = relationship("Violation", back_populates="address", cascade="all, delete-orphan") # Address has many Violations
    businesses = relationship("Business", back_populates="address", cascade="all, delete-orphan") # Address has many Businesses
    address_contacts = relationship("AddressContact", back_populates="address", cascade="all, delete-orphan")
    contacts = relationship("Contact", secondary="address_contacts", back_populates="addresses", overlaps="address_contacts")

# AddressContacts
class AddressContact(Base):
    """
    Association table between Address and Contact.

    Attributes:
        id (int): Primary key.
        address_id (int): Foreign key to the Address table.
        contact_id (int): Foreign key to the Contact table.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        address (Address): Associated address.
        contact (Contact): Associated contact.
    """
    __tablename__ = "address_contacts"

    id = Column(BigInteger, primary_key=True, index=True)
    address_id = Column(BigInteger, ForeignKey('addresses.id'))
    contact_id = Column(BigInteger, ForeignKey('contacts.id'))
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp

    address = relationship("Address", back_populates="address_contacts", overlaps="contacts")
    contact = relationship("Contact", back_populates="address_associations", overlaps="addresses,contacts")


# Areas
class Area(Base):
    """
    Represents an area within an inspection (e.g., a specific room or location).

    Attributes:
        id (int): Primary key.
        name (str): Name of the area.
        notes (str): Notes about the area.
        photos (str): URLs or references to photos of the area.
        inspection_id (int): Foreign key to the Inspection table.
        floor (int): Floor number.
        unit_id (int): Foreign key to the Unit table.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        inspection (Inspection): Associated inspection.
        unit (Unit): Associated unit.
        observations (list[Observation]): Observations made in this area.
    """
    __tablename__ = "areas"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String)
    notes = Column(Text)
    photos = Column(String)
    inspection_id = Column(BigInteger, ForeignKey('inspections.id'), nullable=False)
    floor = Column(Integer)
    unit_id = Column(BigInteger, ForeignKey('units.id'))
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    inspection = relationship("Inspection", back_populates="areas")  # Define relationship to Inspections
    unit = relationship("Unit", back_populates="areas")  # Define relationship to Units
    observations = relationship("Observation", back_populates="area", cascade="all, delete-orphan")  # Area has many Observations

# AreaCodes
class AreaCode(Base):
    """
    Link table between Area and Code.

    Associates a specific code with an area.

    Attributes:
        id (int): Primary key.
        area_id (int): Foreign key to the Area table.
        code_id (int): Foreign key to the Code table.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    __tablename__ = "area_codes"

    id = Column(BigInteger, primary_key=True, index=True)
    area_id = Column(BigInteger, ForeignKey('areas.id'), nullable=False)
    code_id = Column(BigInteger, ForeignKey('codes.id'), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp


# Businesses
class Business(Base):
    """
    Represents a business entity.

    Attributes:
        id (int): Primary key.
        name (str): Business name.
        address_id (int): Foreign key to the Address table.
        unit_id (int): Foreign key to the Unit table.
        website (str): Website URL.
        email (str): Contact email.
        phone (str): Contact phone.
        trading_as (str): DBA name.
        is_closed (bool): Whether the business is closed.
        opened_on (date): Opening date.
        employee_count (int): Number of employees.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        address (Address): Associated address.
        business_contacts (list[BusinessContact]): Link table to contacts.
        contacts (list[Contact]): Associated contacts.
    """
    __tablename__ = "businesses"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String)
    address_id = Column(BigInteger, ForeignKey('addresses.id'), nullable=False)
    unit_id = Column(BigInteger, ForeignKey('units.id'))
    website = Column(String)
    email = Column(String)
    phone = Column(String)
    trading_as = Column(String)
    # New business attributes
    is_closed = Column(Boolean, default=False)
    opened_on = Column(Date)
    employee_count = Column(Integer)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp

    # Relationships
    address = relationship("Address", back_populates="businesses")  # Define relationship to Address
    business_contacts = relationship("BusinessContact", back_populates="business", cascade="all, delete-orphan")
    contacts = relationship("Contact", secondary="business_contacts", back_populates="businesses", overlaps="business_contacts")

# BusinessContacts
class BusinessContact(Base):
    """
    Association table between Business and Contact.

    Attributes:
        id (int): Primary key.
        business_id (int): Foreign key to the Business table.
        contact_id (int): Foreign key to the Contact table.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        business (Business): Associated business.
        contact (Contact): Associated contact.
    """
    __tablename__ = "business_contacts"

    id = Column(BigInteger, primary_key=True, index=True)
    business_id = Column(BigInteger, ForeignKey('businesses.id'), nullable=False)
    contact_id = Column(BigInteger, ForeignKey('contacts.id'), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp

    business = relationship("Business", back_populates="business_contacts", overlaps="contacts")
    contact = relationship("Contact", back_populates="business_associations", overlaps="businesses,contacts")


# Citations
class Citation(Base):
    """
    Represents a citation issued for a violation.

    Attributes:
        id (int): Primary key.
        fine (int): Fine amount.
        deadline (date): Payment or court deadline.
        violation_id (int): Foreign key to the Violation table.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        user_id (int): Foreign key to the User table (issuer).
        status (int): Citation status.
        trial_date (date): Date of the trial.
        code_id (int): Foreign key to the Code table.
        citationid (str): External citation identifier.
        unit_id (int): Foreign key to the Unit table.
        violation (Violation): Associated violation.
        code (Code): Associated code.
        user (User): Associated user.
    """
    __tablename__ = "citations"

    id = Column(BigInteger, primary_key=True, index=True)
    fine = Column(Integer)
    deadline = Column(Date)
    violation_id = Column(BigInteger, ForeignKey('violations.id'), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp

    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    status = Column(Integer)
    trial_date = Column(Date)
    code_id = Column(BigInteger, ForeignKey('codes.id'), nullable=False)
    citationid = Column(String)
    unit_id = Column(BigInteger, ForeignKey('units.id'))

    # Relationships
    violation = relationship("Violation", back_populates="citations") # Citation belongs to a Violation
    # citation has one code 
    code = relationship("Code", back_populates="citations")
    user = relationship("User")  # Add this line to enable joinedload and access to user

# CitationsCodes (join table for Many-to-Many relationships)
class CitationCode(Base):
    """
    Association table between Citation and Code.

    Note: The `Citation` model has a `code_id` FK suggesting a one-to-many relationship,
    but this table supports many-to-many.

    Attributes:
        citation_id (int): Foreign key to the Citation table.
        code_id (int): Foreign key to the Code table.
    """
    __tablename__ = "citations_codes"
    
    citation_id = Column(BigInteger, ForeignKey('citations.id'), primary_key=True, nullable=False)
    code_id = Column(BigInteger, ForeignKey('codes.id'), primary_key=True, nullable=False)


# CitationComments
class CitationComment(Base):
    """
    Comments on a citation.

    Attributes:
        id (int): Primary key.
        user_id (int): Foreign key to the User table.
        citation_id (int): Foreign key to the Citation table.
        content (str): Comment content.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    __tablename__ = "citation_comments"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    citation_id = Column(BigInteger, ForeignKey('citations.id'), nullable=False)
    content = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp


# Codes
class Code(Base):
    """
    Represents a municipal code or ordinance.

    Attributes:
        id (int): Primary key.
        chapter (str): Chapter of the code.
        section (str): Section of the code.
        name (str): Short name or title.
        description (str): Full description or text.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        citations (list[Citation]): Related citations.
        violations (list[Violation]): Related violations.
    """
    __tablename__ = "codes"

    id = Column(BigInteger, primary_key=True, index=True)
    chapter = Column(String)
    section = Column(String)
    name = Column(String)
    description = Column(String)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    citations = relationship("Citation", back_populates="code") # citations have one code
    violations = relationship(
        "Violation",
        secondary="violation_codes",
        back_populates="codes"
    )

# Comments
class Comment(Base):
    """
    General comments associated with an address.

    Attributes:
        id (int): Primary key.
        content (str): Content of the comment.
        address_id (int): Foreign key to the Address table.
        user_id (int): Foreign key to the User table.
        unit_id (int): Foreign key to the Unit table (optional).
        review_later (bool): Flag to mark for later review.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        address (Address): Associated address.
        user (User): Associated user.
        unit (Unit): Associated unit.
    """
    __tablename__ = "comments"
    
    id = Column(BigInteger, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    address_id = Column(BigInteger, ForeignKey('addresses.id'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    unit_id = Column(BigInteger, ForeignKey('units.id'), nullable=True)
    review_later = Column(Boolean, nullable=False, default=False, server_default=text('0'))
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    address = relationship("Address", back_populates="comments")
    user = relationship("User", back_populates="comments")
    unit = relationship("Unit", back_populates="comments")  # Add relationship to Unit

# Concerns
class Concern(Base):
    """
    Represents a concern or complaint lodged by a resident.

    Attributes:
        id (int): Primary key.
        address_id (int): Foreign key to the Address table.
        content (str): Description of the concern.
        emailorphone (str): Contact info of the reporter.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    __tablename__ = "concerns"
    
    id = Column(BigInteger, primary_key=True, index=True)
    address_id = Column(BigInteger, ForeignKey('addresses.id'), nullable=False)
    content = Column(Text)
    emailorphone = Column(String)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp


# Contacts
class Contact(Base):
    """
    Represents a contact person (e.g., owner, property manager).

    Attributes:
        id (int): Primary key.
        name (str): Name of the contact.
        email (str): Email address.
        phone (str): Phone number.
        notes (str): Additional notes.
        hidden (bool): Whether the contact is hidden/archived.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        inspections (list[Inspection]): Related inspections.
        addresses (list[Address]): Related addresses.
        businesses (list[Business]): Related businesses.
    """
    __tablename__ = "contacts"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String)
    email = Column(String)
    phone = Column(String)
    notes = Column(Text, default="")
    hidden = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp


    # Relationships
    inspections = relationship("Inspection", back_populates="contact")  # Define relationship to Inspections
    address_associations = relationship("AddressContact", back_populates="contact", cascade="all, delete-orphan", overlaps="addresses,contacts")
    addresses = relationship("Address", secondary="address_contacts", back_populates="contacts", overlaps="address_associations,contact,address,address_contacts")
    business_associations = relationship("BusinessContact", back_populates="contact", cascade="all, delete-orphan", overlaps="businesses,contacts")
    businesses = relationship("Business", secondary="business_contacts", back_populates="contacts", overlaps="business_associations,business,business_contacts")

# ContactComments
class ContactComment(Base):
    """
    Comments on a contact.

    Attributes:
        id (int): Primary key.
        comment (str): Comment content.
        user_id (int): Foreign key to the User table.
        contact_id (int): Foreign key to the Contact table.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    __tablename__ = "contact_comments"
    
    id = Column(BigInteger, primary_key=True, index=True)
    comment = Column(Text, nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    contact_id = Column(BigInteger, ForeignKey('contacts.id'), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp

# Units
class Unit(Base):
    """
    Represents a unit within an address.

    Attributes:
        id (int): Primary key.
        number (str): Unit number/identifier.
        address_id (int): Foreign key to the Address table.
        vacancy_status (str): Vacancy status.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        areas (list[Area]): Areas within the unit.
        comments (list[Comment]): Comments on the unit.
        violations (list[Violation]): Violations associated with the unit.
    """
    __tablename__ = "units"

    id = Column(BigInteger, primary_key=True, index=True)
    number = Column(String)
    address_id = Column(BigInteger, ForeignKey('addresses.id'), nullable=False)
    vacancy_status = Column(String)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp

    __table_args__ = (UniqueConstraint('number', 'address_id', name='_number_address_uc'),)

    # Relationships
    areas = relationship("Area", back_populates="unit")  # Unit has many Areas
    comments = relationship("Comment", back_populates="unit")  # Unit has many Comments
    # Unit has many Violations
    violations = relationship("Violation", back_populates="unit")

# InspectionCodes
class InspectionCode(Base):
    """
    Association table between Inspection and Code.

    Tracks which codes are relevant to an inspection.

    Attributes:
        id (int): Primary key.
        inspection_id (int): Foreign key to the Inspection table.
        code_id (int): Foreign key to the Code table.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    __tablename__ = "inspection_codes"
    
    id = Column(BigInteger, primary_key=True, index=True)
    inspection_id = Column(BigInteger, ForeignKey('inspections.id'), nullable=False)
    code_id = Column(BigInteger, ForeignKey('codes.id'), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp


# InspectionComments
class InspectionComment(Base):
    """
    Comments on an inspection.

    Attributes:
        id (int): Primary key.
        user_id (int): Foreign key to the User table.
        inspection_id (int): Foreign key to the Inspection table.
        content (str): Comment content.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        user (User): Associated user.
        inspection (Inspection): Associated inspection.
    """
    __tablename__ = "inspection_comments"
    
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    inspection_id = Column(BigInteger, ForeignKey('inspections.id'), nullable=False)
    content = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp

    # Relationships
    user = relationship("User", back_populates="inspection_comments")  # link to user who made comment
    inspection = relationship("Inspection", back_populates="inspection_comments")  # link to inspection

# Inspections
class Inspection(Base):
    """
    Represents an inspection event.

    Attributes:
        id (int): Primary key.
        source (str): Source of the inspection request.
        status (str): Current status.
        attachments (str): URLs or references to attachments.
        result (str): Result of the inspection.
        description (str): Description.
        thoughts (str): Inspector's thoughts/notes.
        originator (str): Originator of the inspection.
        unit_id (int): Foreign key to the Unit table.
        address_id (int): Foreign key to the Address table.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        assignee (str): Assigned inspector name (legacy/text).
        inspector_id (int): Foreign key to the User table (inspector).
        name (str): Name related to inspection.
        email (str): Email related to inspection.
        phone (str): Phone related to inspection.
        scheduled_datetime (datetime): Scheduled date and time.
        photos (str): Photos.
        notes_area_1 (str): Notes for area 1.
        notes_area_2 (str): Notes for area 2.
        notes_area_3 (str): Notes for area 3.
        intphotos (str): Interior photos.
        extphotos (str): Exterior photos.
        contact_id (int): Foreign key to the Contact table.
        new_contact_name (str): Name of a new contact found.
        new_contact_email (str): Email of a new contact found.
        new_contact_phone (str): Phone of a new contact found.
        new_chapter (str): New code chapter referenced.
        new_section (str): New code section referenced.
        new_name (str): New code name referenced.
        new_description (str): New code description referenced.
        confirmed (bool): Confirmation status.
        business_id (int): Foreign key to the Business table.
        start_time (datetime): Actual start time.
        paid (bool): Payment status.
        address (Address): Associated address.
        inspector (User): Associated inspector.
        contact (Contact): Associated contact.
        areas (list[Area]): Areas inspected.
        licenses (list[License]): Licenses related to inspection.
        permits (list[Permit]): Permits related to inspection.
        inspection_comments (list[InspectionComment]): Comments on inspection.
    """
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
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp

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

    # Relationships
    address = relationship("Address", back_populates="inspections")
    inspector = relationship("User", back_populates="inspections")
    contact = relationship("Contact", back_populates="inspections")
    areas = relationship("Area", back_populates="inspection", cascade="all, delete-orphan")  # Inspection has many Areas
    licenses = relationship("License", back_populates="inspection")
    permits = relationship("Permit", back_populates="inspection")
    inspection_comments = relationship("InspectionComment", back_populates="inspection", cascade="all, delete-orphan")  # comments on inspection

# Licenses
class License(Base):
    """
    Represents a business license.

    Attributes:
        id (int): Primary key.
        inspection_id (int): Foreign key to the Inspection table.
        sent (bool): Whether the license has been sent.
        revoked (bool): Whether the license is revoked.
        fiscal_year (str): Fiscal year of the license.
        expiration_date (date): Expiration date.
        license_type (int): Type code.
        business_id (int): Foreign key to the Business table.
        license_number (str): License number.
        date_issued (date): Date issued.
        conditions (str): Conditions of the license.
        paid (bool): Payment status.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        inspection (Inspection): Associated inspection.
    """
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
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp

    inspection = relationship("Inspection", back_populates="licenses")

# Permits
class Permit(Base):
    """
    Represents a permit.

    Attributes:
        id (int): Primary key.
        inspection_id (int): Foreign key to the Inspection table.
        permit_type (str): Type of permit.
        business_id (int): Foreign key to the Business table.
        permit_number (str): Permit number.
        date_issued (date): Date issued.
        expiration_date (date): Expiration date.
        conditions (str): Conditions of the permit.
        paid (bool): Payment status.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        inspection (Inspection): Associated inspection.
    """
    __tablename__ = "permits"

    id = Column(BigInteger, primary_key=True, index=True)
    inspection_id = Column(BigInteger, ForeignKey('inspections.id'), nullable=False)
    # Free-form type label (e.g., "Building/Dumpster/POD permit"); can be normalized later
    permit_type = Column(String)
    business_id = Column(BigInteger, ForeignKey('businesses.id'))
    permit_number = Column(String)
    date_issued = Column(Date)
    expiration_date = Column(Date)
    conditions = Column(Text)
    paid = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp

    inspection = relationship("Inspection", back_populates="permits")
    __table_args__ = (
        UniqueConstraint('inspection_id', name='uq_permits_inspection_id'),
    )


# Notifications
class Notification(Base):
    """
    Represents a user notification.

    Attributes:
        id (int): Primary key.
        title (str): Notification title.
        body (str): Notification body/content.
        inspection_id (int): Foreign key to the Inspection table (optional).
        comment_id (int): Foreign key to the Comment table (optional).
        user_id (int): Foreign key to the User table.
        read (bool): Read status.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    __tablename__ = "notifications"
    
    id = Column(BigInteger, primary_key=True, index=True)
    title = Column(String)
    body = Column(Text)
    # allow notifications to be linked to an inspection OR a comment (or neither)
    inspection_id = Column(BigInteger, ForeignKey('inspections.id'), nullable=True)
    comment_id = Column(BigInteger, ForeignKey('comments.id'), nullable=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp


# Mentions (when a user is @-mentioned in a comment)
class Mention(Base):
    """
    Represents a user mention in a comment.

    Attributes:
        id (int): Primary key.
        comment_id (int): Foreign key to the Comment table.
        user_id (int): Foreign key to the User table (recipient).
        actor_id (int): Foreign key to the User table (sender).
        is_read (bool): Read status.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    __tablename__ = "mentions"

    id = Column(BigInteger, primary_key=True, index=True)
    comment_id = Column(BigInteger, ForeignKey('comments.id'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)  # recipient
    actor_id = Column(BigInteger, ForeignKey('users.id'), nullable=True)  # who mentioned
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


# Links a general Comment to one or more Contacts when %Contact mentions are used
class CommentContactLink(Base):
    """
    Link table between Comment and Contact (mentions).

    Used when a contact is mentioned in a comment.

    Attributes:
        id (int): Primary key.
        comment_id (int): Foreign key to the Comment table.
        contact_id (int): Foreign key to the Contact table.
        actor_id (int): Foreign key to the User table (who mentioned).
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    __tablename__ = "comment_contact_links"

    id = Column(BigInteger, primary_key=True, index=True)
    comment_id = Column(BigInteger, ForeignKey('comments.id', ondelete='CASCADE'), nullable=False)
    contact_id = Column(BigInteger, ForeignKey('contacts.id', ondelete='CASCADE'), nullable=False)
    actor_id = Column(BigInteger, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


# Observations
class Observation(Base):
    """
    Represents an observation made during an inspection in a specific area.

    Attributes:
        id (int): Primary key.
        content (str): Observation content/description.
        area_id (int): Foreign key to the Area table.
        potentialvio (bool): Whether it is a potential violation.
        user_id (int): Foreign key to the User table (observer).
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        area (Area): Associated area.
        user (User): Associated user.
        photos (list[Photo]): Photos of the observation.
        codes (list[Code]): Suspected codes.
    """
    __tablename__ = "observations"
    
    id = Column(BigInteger, primary_key=True, index=True)
    content = Column(Text)
    area_id = Column(BigInteger, ForeignKey('areas.id'), nullable=False)
    potentialvio = Column(Boolean)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp

    # Relationships
    area = relationship("Area", back_populates="observations")  # Observation belongs to an Area
    user = relationship("User", back_populates="observations")  # Observation belongs to a User
    photos = relationship("Photo", back_populates="observation", cascade="all, delete-orphan")  # Observation has many Photos
    # Many-to-many suspected codes
    codes = relationship(
        "Code",
        secondary="observation_codes",
        backref="observations"
    )

# Photos
class Photo(Base):
    """
    Represents a photo linked to an observation.

    Attributes:
        id (int): Primary key.
        url (str): URL of the photo.
        observation_id (int): Foreign key to the Observation table.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        observation (Observation): Associated observation.
    """
    __tablename__ = "photos"
    
    id = Column(BigInteger, primary_key=True, index=True)
    url = Column(String, nullable=False)
    observation_id = Column(BigInteger, ForeignKey('observations.id'), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated

    # Relationships
    observation = relationship("Observation", back_populates="photos")  # Photo belongs to an Observation

# ObservationCodes (join table for suspected codes per Observation)
class ObservationCode(Base):
    """
    Association table between Observation and Code.

    Tracks suspected codes for an observation.

    Attributes:
        observation_id (int): Foreign key to the Observation table.
        code_id (int): Foreign key to the Code table.
    """
    __tablename__ = "observation_codes"

    observation_id = Column(BigInteger, ForeignKey('observations.id'), primary_key=True, nullable=False)
    code_id = Column(BigInteger, ForeignKey('codes.id'), primary_key=True, nullable=False)

# Prompts
class Prompt(Base):
    """
    Represents a prompt for a room during inspection.

    Attributes:
        id (int): Primary key.
        content (str): The prompt text.
        room_id (int): Foreign key to the Room table.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        room (Room): Associated room.
    """
    __tablename__ = "prompts"
    
    id = Column(BigInteger, primary_key=True, index=True)
    content = Column(String)
    room_id = Column(BigInteger, ForeignKey('rooms.id'), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp

    # Relationships
    room = relationship("Room", back_populates="prompts")  # Prompt belongs to a Room

# Rooms
class Room(Base):
    """
    Represents a type of room (e.g., "Kitchen", "Bathroom").

    Attributes:
        id (int): Primary key.
        name (str): Room name.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        prompts (list[Prompt]): Associated prompts.
    """
    __tablename__ = "rooms"
    
    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp

    # Relationships
    prompts = relationship("Prompt", back_populates="room")  # Room has many Prompts

# UnitContacts
class UnitContact(Base):
    """
    Association table between Unit and Contact.

    Attributes:
        id (int): Primary key.
        unit_id (int): Foreign key to the Unit table.
        contact_id (int): Foreign key to the Contact table.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    __tablename__ = "unit_contacts"
    
    id = Column(BigInteger, primary_key=True, index=True)
    unit_id = Column(BigInteger, ForeignKey('units.id'), nullable=False)
    contact_id = Column(BigInteger, ForeignKey('contacts.id'), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp


# Users
class User(Base):
    """
    Represents a system user.

    Attributes:
        id (int): Primary key.
        email (str): Email address (unique).
        encrypted_password (str): Encrypted password.
        reset_password_token (str): Token for password reset.
        reset_password_sent_at (datetime): Timestamp when reset token was sent.
        remember_created_at (datetime): Timestamp for remember-me functionality.
        name (str): User name.
        phone (str): User phone.
        role (int): User role (e.g., 0 for standard, 3 for admin).
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        inspections (list[Inspection]): Inspections assigned to user.
        comments (list[Comment]): Comments made by user.
        observations (list[Observation]): Observations made by user.
        inspection_comments (list[InspectionComment]): Inspection comments made by user.
    """
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
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp


    # Relationships
    inspections = relationship("Inspection", back_populates="inspector")  # Define relationship to Inspections
    comments = relationship("Comment", back_populates="user")  # Define relationship to Comments
    observations = relationship("Observation", back_populates="user")  # Define relationship to Observations
    inspection_comments = relationship("InspectionComment", back_populates="user")  # comments made by user on inspections

# Versions
class Version(Base):
    """
    Represents a version history record (PaperTrail style).

    Attributes:
        id (int): Primary key.
        item_type (str): Type of the item (table name).
        item_id (int): ID of the item.
        event (str): Event type (create, update, destroy).
        whodunnit (str): Who performed the action.
        object (str): Serialized object state.
        created_at (datetime): Creation timestamp.
    """
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
    """
    Association table between Violation and Code.

    Attributes:
        id (int): Primary key.
        violation_id (int): Foreign key to the Violation table.
        code_id (int): Foreign key to the Code table.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    __tablename__ = "violation_codes"
    
    id = Column(BigInteger, primary_key=True, index=True)
    violation_id = Column(BigInteger, ForeignKey('violations.id'), nullable=False)
    code_id = Column(BigInteger, ForeignKey('codes.id'), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp


# ViolationComments
class ViolationComment(Base):
    """
    Comments on a violation.

    Attributes:
        id (int): Primary key.
        violation_id (int): Foreign key to the Violation table.
        user_id (int): Foreign key to the User table.
        content (str): Comment content.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        user (User): Associated user.
    """
    __tablename__ = "violation_comments"
    
    id = Column(BigInteger, primary_key=True, index=True)
    violation_id = Column(BigInteger, ForeignKey('violations.id'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    content = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp

    # Relationship to User
    user = relationship("User", backref="violation_comments")


# Violations
class Violation(Base):
    """
    Represents a code violation.

    Attributes:
        id (int): Primary key.
        description (str): Description of the violation.
        status (int): Status code.
        address_id (int): Foreign key to the Address table.
        user_id (int): Foreign key to the User table (issuer).
        deadline (str): Deadline string (e.g. "30 days").
        violation_type (str): Type of violation.
        extend (int): Extension days granted.
        unit_id (int): Foreign key to the Unit table.
        inspection_id (int): Foreign key to the Inspection table.
        comment (str): Additional comment.
        business_id (int): Foreign key to the Business table.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        citations (list[Citation]): Citations issued for this violation.
        address (Address): Associated address.
        codes (list[Code]): Codes violated.
        violation_comments (list[ViolationComment]): Comments on the violation.
        user (User): Associated user.
        unit (Unit): Associated unit.
    """
    __tablename__ = "violations"
    
    id = Column(BigInteger, primary_key=True, index=True)
    description = Column(String)
    status = Column(Integer)
    address_id = Column(BigInteger, ForeignKey('addresses.id'), nullable=False)
    citations = relationship("Citation", backref="violation", cascade="all, delete-orphan")
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    deadline = Column(String)
    violation_type = Column(String)
    extend = Column(Integer, default=0)
    unit_id = Column(BigInteger, ForeignKey('units.id'))
    inspection_id = Column(BigInteger, ForeignKey('inspections.id'))
    comment = Column(Text)
    business_id = Column(BigInteger)
    created_at = Column(DateTime, default=func.now(), nullable=False)  # Auto-generate created_at timestamp
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)  # Auto-update updated_at timestamp


    # Relationships
    address = relationship("Address", back_populates="violations") # Violation belongs to an Address
    citations = relationship("Citation", back_populates="violation") # Violation has many Citations
    codes = relationship(
        "Code",
        secondary="violation_codes",
        back_populates="violations"
    )
    violation_comments = relationship("ViolationComment", backref="violation", cascade="all, delete-orphan") # Violation has many ViolationComments
    user = relationship("User")  # Add this line to enable joinedload and access to user
    # Relationship to Unit (optional)
    unit = relationship("Unit", back_populates="violations")

    def deadline_passed(self) -> bool:
        """
        Determine if the deadline has passed.

        Returns:
            bool: True if the deadline has passed, False otherwise.
        """
        deadline_index = DEADLINE_OPTIONS.index(self.deadline) if self.deadline in DEADLINE_OPTIONS else None
        if deadline_index is None:
            return False
        deadline_days = DEADLINE_VALUES[deadline_index]
        deadline_date = self.created_at + timedelta(days=deadline_days) + timedelta(days=self.extend)
        return deadline_date < datetime.utcnow()

    @property
    def deadline_date(self) -> datetime:
        """
        Calculate the actual deadline date.

        Returns:
            datetime: The calculated deadline date including extensions.

        Raises:
            ValueError: If the deadline value is invalid.
        """
        deadline_index = DEADLINE_OPTIONS.index(self.deadline) if self.deadline in DEADLINE_OPTIONS else None
        if deadline_index is None:
            raise ValueError("Invalid deadline value")
        deadline_days = DEADLINE_VALUES[deadline_index]
        return self.created_at + timedelta(days=deadline_days) + timedelta(days=self.extend)
