"""
Pydantic schemas for request and response models.

This module contains the Pydantic models used for data validation and serialization
across the API.
"""

from pydantic import BaseModel, validator, Field
from typing import Optional, List
from datetime import datetime, date
from constants import DEADLINE_OPTIONS, DEADLINE_VALUES

# Ensure CodeResponse is defined before ViolationResponse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schemas import CodeResponse

# Pydantic schema for address
class AddressCreate(BaseModel):
    """
    Schema for creating or updating an address.

    Attributes:
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
    """
    pid: Optional[str] = None
    ownername: Optional[str] = None
    owneraddress: Optional[str] = None
    ownercity: Optional[str] = None
    ownerstate: Optional[str] = None
    ownerzip: Optional[str] = None
    streetnumb: Optional[str] = None
    streetname: Optional[str] = None
    streettype: Optional[str] = None
    landusecode: Optional[str] = None
    zoning: Optional[str] = None
    owneroccupiedin: Optional[str] = None
    vacant: Optional[str] = None
    absent: Optional[str] = None
    premisezip: Optional[str] = None
    combadd: Optional[str] = None
    outstanding: Optional[bool] = False
    name: Optional[str] = None
    proptype: Optional[int] = 1
    property_type: Optional[str] = None
    property_name: Optional[str] = None
    aka: Optional[str] = None
    district: Optional[str] = None
    property_id: Optional[str] = None
    vacancy_status: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class AddressResponse(AddressCreate):
    """
    Schema for address response.

    Attributes:
        id (int): Address ID.
        combadd (str): Combined address string.
        ownername (str): Owner's name.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    id: int
    combadd: Optional[str] = None
    ownername: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SDATRefreshRequest(BaseModel):
    """
    Schema for SDAT refresh request.

    Attributes:
        county (str): County identifier.
        district (str): District identifier.
        account_number (str): Account number.
    """
    county: Optional[str] = None
    district: Optional[str] = None
    account_number: Optional[str] = None


class SDATRefreshResponse(BaseModel):
    """
    Schema for SDAT refresh response.

    Attributes:
        address (AddressResponse): The updated address object.
        updated_fields (list[str]): List of fields that were updated.
        source_url (str): Source URL of the data.
        mailing_lines (list[str]): Mailing lines extracted.
    """
    address: AddressResponse
    updated_fields: List[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    mailing_lines: List[str] = Field(default_factory=list)


# Pydantic schema for User
class UserBase(BaseModel):
    """
    Base schema for user data.

    Attributes:
        email (str): User email.
        name (str): User name.
        phone (str): User phone number.
        role (int): User role code.
    """
    email: str
    name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[int] = 0

class UserCreate(UserBase):
    """
    Schema for creating a new user.

    Attributes:
        password (str): User password.
    """
    password: str

class UserResponse(UserBase):
    """
    Schema for user response.

    Attributes:
        id (int): User ID.
        name (str): User name.
        email (str): User email.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    id: int
    name: Optional[str] = None
    email: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserUpdate(UserBase):
    """
    Schema for updating a user.

    Attributes:
        password (str): New password (optional).
    """
    password: Optional[str] = None

class PasswordResetRequest(BaseModel):
    """
    Schema for password reset request.

    Attributes:
        email (str): Email of the user requesting reset.
    """
    email: str

class PasswordResetConfirm(BaseModel):
    """
    Schema for password reset confirmation.

    Attributes:
        token (str): Reset token.
        password (str): New password.
    """
    token: str
    password: str

# Pydantic schema for Business
class BusinessBase(BaseModel):
    """
    Base schema for business data.

    Attributes:
        name (str): Business name.
        address_id (int): Address ID.
        unit_id (int): Unit ID (optional).
        website (str): Website URL.
        email (str): Contact email.
        phone (str): Contact phone.
        trading_as (str): DBA name.
        is_closed (bool): Whether the business is closed.
        opened_on (date): Opening date.
        employee_count (int): Number of employees.
    """
    name: Optional[str] = None
    address_id: int
    unit_id: Optional[int] = None
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    trading_as: Optional[str] = None
    # New fields
    is_closed: Optional[bool] = False
    opened_on: Optional[date] = None
    employee_count: Optional[int] = None

class BusinessCreate(BusinessBase):
    """Schema for creating a new business."""
    pass

class BusinessResponse(BusinessBase):
    """
    Schema for business response.

    Attributes:
        id (int): Business ID.
        address_id (int): Address ID.
        address (AddressResponse): Associated address.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    id: int
    address_id: int
    address: Optional[AddressResponse] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Pydantic schema for Contact
class ContactBase(BaseModel):
    """
    Base schema for contact data.

    Attributes:
        name (str): Contact name.
        email (str): Contact email.
        phone (str): Contact phone.
        notes (str): Notes.
        hidden (bool): Whether the contact is hidden.
    """
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = ""
    hidden: Optional[bool] = False

class ContactCreate(ContactBase):
    """Schema for creating a new contact."""
    pass

class ContactResponse(ContactBase):
    """
    Schema for contact response.

    Attributes:
        id (int): Contact ID.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InspectionSummary(BaseModel):
    """
    Summary schema for inspection data.

    Attributes:
        id (int): Inspection ID.
        address_id (int): Address ID.
        address (AddressResponse): Associated address.
        source (str): Source of inspection.
        status (str): Inspection status.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    id: int
    address_id: int
    address: Optional[AddressResponse] = None
    source: Optional[str] = None
    status: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PermitSummary(BaseModel):
    """
    Summary schema for permit data.

    Attributes:
        id (int): Permit ID.
        inspection_id (int): Inspection ID.
        permit_type (str): Type of permit.
        permit_number (str): Permit number.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    id: int
    inspection_id: int
    permit_type: Optional[str] = None
    permit_number: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContactDetailResponse(ContactResponse):
    """
    Detailed schema for contact response including related entities.

    Attributes:
        addresses (list[AddressResponse]): Linked addresses.
        businesses (list[BusinessResponse]): Linked businesses.
        inspections (list[InspectionSummary]): Linked inspections.
        permits (list[PermitSummary]): Linked permits.
        complaints (list[InspectionSummary]): Linked complaints.
    """
    addresses: List[AddressResponse] = Field(default_factory=list)
    businesses: List[BusinessResponse] = Field(default_factory=list)
    inspections: List[InspectionSummary] = Field(default_factory=list)
    permits: List[PermitSummary] = Field(default_factory=list)
    complaints: List[InspectionSummary] = Field(default_factory=list)

# Pydantic schema for Violations
class ViolationBase(BaseModel):
    """
    Base schema for violation data.

    Attributes:
        description (str): Description of the violation.
        status (int): Status code.
        address_id (int): Address ID.
        user_id (int): User ID (issuer).
        deadline (str): Deadline string.
        violation_type (str): Type of violation.
        extend (int): Extension days.
        unit_id (int): Unit ID.
        inspection_id (int): Inspection ID.
        business_id (int): Business ID.
        comment (str): Additional comment.
    """
    description: Optional[str] = None
    status: Optional[int] = None
    address_id: int
    user_id: int
    deadline: Optional[str] = None
    violation_type: Optional[str] = None
    extend: Optional[int] = 0
    unit_id: Optional[int] = None
    inspection_id: Optional[int] = None
    business_id: Optional[int] = None
    comment: Optional[str] = None

    @validator('deadline')
    def validate_deadline(cls, value):
        if value not in DEADLINE_OPTIONS:
            raise ValueError(f"Invalid deadline value: {value}")
        return value

class ViolationCreate(ViolationBase):
    """
    Schema for creating a new violation.

    Attributes:
        codes (list[int]): List of code IDs violated.
    """
    codes: Optional[List[int]] = None  # Accept a list of code IDs when creating


class ViolationFromCommentRequest(BaseModel):
    """
    Payload for drafting a violation from an existing comment.

    Attributes:
        deadline (str): Deadline string.
        codes (list[int]): List of code IDs.
        user_id (int): User ID.
        violation_type (str): Violation type.
        status (int): Status code.
        description (str): Description.
        comment (str): Comment content.
        keep_filenames (list[str]): List of filenames to keep.
    """
    deadline: Optional[str] = None
    codes: Optional[List[int]] = None
    user_id: Optional[int] = None
    violation_type: Optional[str] = None
    status: Optional[int] = None
    description: Optional[str] = None
    comment: Optional[str] = None
    keep_filenames: Optional[List[str]] = None

    @validator("deadline")
    def validate_deadline(cls, value):
        if value is None:
            return value
        if value not in DEADLINE_OPTIONS:
            raise ValueError(f"Invalid deadline value: {value}")
        return value


class ViolationResponse(ViolationBase):
    """
    Schema for violation response.

    Attributes:
        id (int): Violation ID.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        combadd (str): Combined address string.
        deadline_date (datetime): Calculated deadline date.
        codes (list[CodeResponse]): Violated codes.
        violation_comments (list[ViolationCommentResponse]): Comments on violation.
        user (UserResponse): User who issued violation.
        unit (UnitResponse): Associated unit.
    """
    id: int
    created_at: datetime
    updated_at: datetime
    combadd: Optional[str] = None
    deadline_date: Optional[datetime]  # Include the deadline date in the response
    codes: Optional[List['CodeResponse']] = None
    violation_comments: Optional[List['ViolationCommentResponse']] = None
    user: Optional[UserResponse] = None  # <-- Add this line
    unit: Optional['UnitResponse'] = None

    class Config:
        from_attributes = True

# Pydantic schema for Comments
class CommentBase(BaseModel):
    """
    Base schema for comment data.

    Attributes:
        content (str): Content of the comment.
        user_id (int): ID of the user creating the comment.
        address_id (int): ID of the address associated with the comment.
        unit_id (int): ID of the unit associated with the comment (optional).
        review_later (bool): Whether to flag the comment for later review.
    """
    content: str
    user_id: int
    address_id: int  # Address ID is required
    unit_id: Optional[int] = None  # Unit ID is optional
    review_later: bool = False

# Schema for creating a new comment (doesn't include id, created_at, updated_at)
class CommentCreate(CommentBase):
    """Schema for creating a new comment."""
    pass  # Inherit all fields from CommentBase for creation

class CommentReviewUpdate(BaseModel):
    """
    Schema for updating the review status of a comment.

    Attributes:
        review_later (bool): Whether to flag the comment for later review.
    """
    review_later: bool

# Schema for returning comment data in API responses
class CommentResponse(CommentBase):
    """
    Schema for comment response.

    Attributes:
        id (int): Comment ID.
        content (str): Content of the comment.
        user_id (int): User ID.
        address_id (int): Address ID.
        user (UserResponse): User details.
        unit_id (int): Unit ID.
        combadd (str): Combined address string.
        mentions (list[UserResponse]): Users mentioned in the comment.
        contact_mentions (list[ContactResponse]): Contacts mentioned in the comment.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    id: int
    content: str
    user_id: int
    address_id: int
    user: UserResponse  # Include the user response here for returning full user data
    unit_id: Optional[int] = None
    combadd: Optional[str] = None
    mentions: Optional[List[UserResponse]] = None
    contact_mentions: Optional[List[ContactResponse]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # This allows returning ORM models as dicts


class CommentPageResponse(BaseModel):
    """
    Schema for paginated comment responses.

    Attributes:
        results (list[CommentResponse]): List of comments.
        total (int): Total number of comments.
        page (int): Current page number.
        page_size (int): Number of items per page.
        has_more (bool): Whether there are more pages.
    """
    results: List[CommentResponse]
    total: int
    page: int
    page_size: int
    has_more: bool

# Pydantic schema for Citations
class CitationBase(BaseModel):
    """
    Base schema for citation data.

    Attributes:
        fine (float): Fine amount.
        deadline (date): Deadline for payment/court.
        violation_id (int): Violation ID.
        user_id (int): User ID (issuer).
        status (int): Citation status.
        trial_date (date): Trial date.
        code_id (int): Code ID.
        citationid (str): External citation ID.
        unit_id (int): Unit ID.
    """
    fine: Optional[float] = None
    deadline: Optional[date] = None
    violation_id: int
    user_id: int
    status: Optional[int] = None
    trial_date: Optional[date] = None
    code_id: Optional[int] = None
    citationid: Optional[str] = None
    unit_id: Optional[int] = None

class CitationCreate(CitationBase):
    """Schema for creating a new citation."""
    pass

class CitationResponse(BaseModel):
    """
    Schema for citation response.

    Attributes:
        id (int): Citation ID.
        violation_id (int): Violation ID.
        deadline (date): Deadline.
        fine (float): Fine amount.
        citationid (str): External citation ID.
        status (int): Status code.
        trial_date (date): Trial date.
        code_id (int): Code ID.
        code_name (str): Code name.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        combadd (str): Combined address string.
        user (UserResponse): User details.
    """
    id: int
    violation_id: int  # Link to the violation
    deadline: Optional[date] = None
    fine: Optional[float] = None
    citationid: Optional[str] = None
    status: Optional[int] = None
    trial_date: Optional[date] = None
    code_id: Optional[int] = None
    code_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    combadd: Optional[str] = None  # Add combadd attribute
    user: Optional[UserResponse] = None  # Add user to response

    class Config:
        from_attributes = True

# Pydantic schema for Inspections
class InspectionBase(BaseModel):
    """
    Base schema for inspection data.

    Attributes:
        address_id (int): Address ID.
        contact_id (int): Contact ID (optional).
        status (int): Status code (optional).
        source (str): Source of inspection request.
        unit_id (int): Unit ID (optional).
        business_id (int): Business ID (optional).
        description (str): Description.
    """
    address_id: int
    contact_id: Optional[int] = None
    status: Optional[int] = None
    source: str
    unit_id: Optional[int] = None
    business_id: Optional[int] = None
    description: Optional[str] = None

class InspectionCreate(InspectionBase):
    """Schema for creating a new inspection."""
    pass

class InspectionResponse(BaseModel):
    """
    Schema for inspection response.

    Attributes:
        id (int): Inspection ID.
        address_id (int): Address ID.
        address (AddressResponse): Associated address.
        inspector_id (int): Inspector ID.
        inspector (UserResponse): Inspector details.
        status (str): Inspection status.
        source (str): Source of inspection.
        description (str): Description.
        scheduled_datetime (datetime): Scheduled time.
        unit_id (int): Unit ID.
        business_id (int): Business ID.
        comment (str): Comment.
        contact (ContactResponse): Contact details.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        status_message (str): Ephemeral status message.
    """
    id: int
    address_id: int
    address: Optional[AddressResponse] = None
    inspector_id: Optional[int] = None
    inspector: Optional[UserResponse] = None
    status: Optional[str] = None
    source: Optional[str] = None
    description: Optional[str] = None
    scheduled_datetime: Optional[datetime] = None
    unit_id: Optional[int] = None
    business_id: Optional[int] = None
    comment: Optional[str] = None
    contact: Optional[ContactResponse] = None
    created_at: datetime
    updated_at: datetime
    status_message: Optional[str] = None  # ephemeral message about side-effects (e.g., license creation)

    class Config:
        from_attributes = True

# --- Inspection comment schemas ---
class InspectionCommentBase(BaseModel):
    """
    Base schema for inspection comment.

    Attributes:
        content (str): Comment content.
        user_id (int): User ID.
    """
    content: str
    user_id: int


class InspectionCommentCreate(InspectionCommentBase):
    """Schema for creating a new inspection comment."""
    pass


class InspectionCommentResponse(InspectionCommentBase):
    """
    Schema for inspection comment response.

    Attributes:
        id (int): Comment ID.
        inspection_id (int): Inspection ID.
        user (UserResponse): User details.
        mentions (list[UserResponse]): Mentioned users.
        contact_mentions (list[ContactResponse]): Mentioned contacts.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    id: int
    inspection_id: int
    user: Optional[UserResponse] = None
    mentions: Optional[List[UserResponse]] = None
    contact_mentions: Optional[List[ContactResponse]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Pydantic schema for Codes
class CodeBase(BaseModel):
    """
    Base schema for code data.

    Attributes:
        chapter (str): Chapter string.
        section (str): Section string.
        name (str): Short name.
        description (str): Full description.
    """
    chapter: str
    section: str
    name: str
    description: str

class CodeCreate(CodeBase):
    """Schema for creating a new code."""
    pass

class CodeViolationSummary(BaseModel):
    """
    Summary schema for violations linked to a code.

    Attributes:
        id (int): Violation ID.
        description (str): Description.
        status (int): Status code.
        address_id (int): Address ID.
        inspection_id (int): Inspection ID.
        business_id (int): Business ID.
        deadline (str): Deadline string.
        deadline_date (datetime): Deadline date.
        combadd (str): Combined address string.
        violation_type (str): Violation type.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    id: int
    description: Optional[str] = None
    status: Optional[int] = None
    address_id: int
    inspection_id: Optional[int] = None
    business_id: Optional[int] = None
    deadline: Optional[str] = None
    deadline_date: Optional[datetime] = None
    combadd: Optional[str] = None
    violation_type: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CodePublic(CodeBase):
    """
    Public schema for code data.

    Attributes:
        id (int): Code ID.
        name (str): Code name.
        chapter (str): Chapter.
        section (str): Section.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    id: int
    name: str
    chapter: str
    section: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CodeResponse(CodePublic):
    """
    Extended schema for code response including usage stats.

    Attributes:
        violation_count (int): Count of violations using this code.
        violations (list[CodeViolationSummary]): List of recent violations.
    """
    violation_count: int = 0
    violations: Optional[List[CodeViolationSummary]] = None

# Licenses
class LicenseBase(BaseModel):
    """
    Base schema for license data.

    Attributes:
        inspection_id (int): Inspection ID (optional).
        sent (bool): Sent status.
        paid (bool): Paid status.
        license_type (int): Type code.
        business_id (int): Business ID (optional).
        date_issued (date): Date issued.
        expiration_date (date): Expiration date.
        fiscal_year (str): Fiscal year.
        license_number (str): License number.
        conditions (str): Conditions.
        revoked (bool): Revoked status.
    """
    inspection_id: Optional[int] = None
    sent: Optional[bool] = False
    paid: bool
    license_type: int
    business_id: Optional[int] = None
    date_issued: Optional[date] = None
    expiration_date: Optional[date] = None
    fiscal_year: Optional[str] = None
    license_number: Optional[str] = None
    conditions: Optional[str] = None
    revoked: Optional[bool] = None

class LicenseCreate(LicenseBase):
    """
    Schema for creating a new license.

    Attributes:
        address_id (int): Address ID (optional).
    """
    address_id: Optional[int] = None

class LicenseResponse(LicenseBase):
    """
    Schema for license response.

    Attributes:
        id (int): License ID.
        inspection_id (int): Inspection ID.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        address_id (int): Address ID.
        combadd (str): Combined address string.
    """
    inspection_id: int
    id: int
    created_at: datetime
    updated_at: datetime
    address_id: Optional[int] = None
    combadd: Optional[str] = None  # address combined

    class Config:
        from_attributes = True

class LicenseUpdate(BaseModel):
    """
    Schema for updating a license.

    Attributes:
        sent (bool): Sent status.
        paid (bool): Paid status.
        license_type (int): Type code.
        business_id (int): Business ID.
        date_issued (date): Date issued.
        expiration_date (date): Expiration date.
        fiscal_year (str): Fiscal year.
        license_number (str): License number.
        conditions (str): Conditions.
        revoked (bool): Revoked status.
    """
    sent: Optional[bool] = None
    paid: Optional[bool] = None
    license_type: Optional[int] = None
    business_id: Optional[int] = None
    date_issued: Optional[date] = None
    expiration_date: Optional[date] = None
    fiscal_year: Optional[str] = None
    license_number: Optional[str] = None
    conditions: Optional[str] = None
    revoked: Optional[bool] = None

# Permits
class PermitBase(BaseModel):
    """
    Base schema for permit data.

    Attributes:
        inspection_id (int): Inspection ID.
        permit_type (str): Permit type.
        business_id (int): Business ID (optional).
        permit_number (str): Permit number.
        date_issued (date): Date issued.
        expiration_date (date): Expiration date.
        conditions (str): Conditions.
        paid (bool): Paid status.
    """
    inspection_id: int
    permit_type: Optional[str] = None
    business_id: Optional[int] = None
    permit_number: Optional[str] = None
    date_issued: Optional[date] = None
    expiration_date: Optional[date] = None
    conditions: Optional[str] = None
    paid: bool = False

class PermitCreate(PermitBase):
    """Schema for creating a new permit."""
    pass

class PermitResponse(PermitBase):
    """
    Schema for permit response.

    Attributes:
        id (int): Permit ID.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        address_id (int): Address ID.
        combadd (str): Combined address string.
    """
    id: int
    created_at: datetime
    updated_at: datetime
    address_id: Optional[int] = None
    combadd: Optional[str] = None

    class Config:
        from_attributes = True


class PermitUpdate(BaseModel):
    """
    Schema for updating a permit.

    Attributes:
        permit_type (str): Permit type.
        business_id (int): Business ID.
        permit_number (str): Permit number.
        date_issued (date): Date issued.
        expiration_date (date): Expiration date.
        conditions (str): Conditions.
        paid (bool): Paid status.
    """
    permit_type: Optional[str] = None
    business_id: Optional[int] = None
    permit_number: Optional[str] = None
    date_issued: Optional[date] = None
    expiration_date: Optional[date] = None
    conditions: Optional[str] = None
    paid: Optional[bool] = None


class RecentActivityResponse(BaseModel):
    """
    Schema for recent activity dashboard response.

    Attributes:
        comments (list[CommentResponse]): Recent comments.
        inspections (list[InspectionResponse]): Recent inspections.
        complaints (list[InspectionResponse]): Recent complaints.
        licenses (list[LicenseResponse]): Recent licenses.
        permits (list[PermitResponse]): Recent permits.
        violations (list[ViolationResponse]): Recent violations.
    """
    comments: List[CommentResponse]
    inspections: List[InspectionResponse]
    complaints: List[InspectionResponse]
    licenses: List[LicenseResponse]
    permits: List[PermitResponse]
    violations: List[ViolationResponse]


class OasDashboardResponse(BaseModel):
    """
    Schema for OAS dashboard response.

    Attributes:
        pending_complaints (list[InspectionResponse]): Pending complaints.
        active_violations (list[ViolationResponse]): Active violations.
        active_violations_count (int): Count of active violations.
        licenses_needing_action_count (int): Count of licenses needing action.
        licenses_not_paid (list[LicenseResponse]): Unpaid licenses.
        licenses_not_sent (list[LicenseResponse]): Unsent licenses.
    """
    pending_complaints: List[InspectionResponse]
    active_violations: List[ViolationResponse]
    active_violations_count: int = 0
    licenses_needing_action_count: int = 0
    licenses_not_paid: List[LicenseResponse]
    licenses_not_sent: List[LicenseResponse]


# Pydantic schema for ContactComments
class ContactCommentBase(BaseModel):
    """
    Base schema for contact comments.

    Attributes:
        contact_id (int): Contact ID.
        comment (str): Comment content.
        user_id (int): User ID.
    """
    contact_id: int
    comment: str
    user_id: int

class ContactCommentCreate(ContactCommentBase):
    """Schema for creating a new contact comment."""
    pass

class ContactCommentResponse(ContactCommentBase):
    """
    Schema for contact comment response.

    Attributes:
        id (int): Comment ID.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Pydantic schema for Areas
class AreaBase(BaseModel):
    """
    Base schema for area data.

    Attributes:
        name (str): Area name.
        notes (str): Notes.
        photos (list[str]): List of photo URLs.
    """
    name: str
    notes: Optional[str] = None
    photos: Optional[List[str]] = None

class AreaCreate(AreaBase):
    """
    Schema for creating a new area.

    Attributes:
        unit_id (int): Unit ID (optional).
    """
    unit_id: Optional[int] = None

class AreaResponse(AreaBase):
    """
    Schema for area response.

    Attributes:
        id (int): Area ID.
        inspection_id (int): Inspection ID.
        unit_id (int): Unit ID.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    id: int
    name: str
    inspection_id: int
    notes: Optional[str] = None
    photos: Optional[List[str]] = None
    unit_id: Optional[int] = None  # Include the unit_id field
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Pydantic schema for Units
class UnitBase(BaseModel):
    """
    Base schema for unit data.

    Attributes:
        number (str): Unit number.
    """
    number: str

class UnitCreate(UnitBase):
    """Schema for creating a new unit."""
    pass

class UnitResponse(UnitBase):
    """
    Schema for unit response.

    Attributes:
        id (int): Unit ID.
        address_id (int): Address ID.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    id: int
    number: str
    address_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Response schema for per-unit aggregated alert counts
class UnitAlertCountsResponse(BaseModel):
    """
    Schema for per-unit aggregated alert counts.

    Attributes:
        unit_id (int): Unit ID.
        unit_number (str): Unit number.
        pending_inspections (int): Count of pending inspections.
        open_violations (int): Count of open violations.
        unpaid_citations (int): Count of unpaid citations.
    """
    unit_id: int
    unit_number: Optional[str] = None
    pending_inspections: int = 0
    open_violations: int = 0
    unpaid_citations: int = 0

    class Config:
        from_attributes = True

# Pydantic schema for Rooms
class RoomBase(BaseModel):
    """
    Base schema for room data.

    Attributes:
        name (str): Room name.
    """
    name: str
    
class RoomCreate(RoomBase):
    """Schema for creating a new room."""
    pass

class RoomResponse(RoomBase):
    """
    Schema for room response.

    Attributes:
        id (int): Room ID.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    id: int
    name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Pydantic schema for Prompts
class PromptBase(BaseModel):
    """
    Base schema for prompt data.

    Attributes:
        content (str): Prompt content.
    """
    content: str

class PromptCreate(PromptBase):
    """Schema for creating a new prompt."""
    pass

class PromptResponse(PromptBase):
    """
    Schema for prompt response.

    Attributes:
        id (int): Prompt ID.
        room_id (int): Room ID.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    id: int
    content: str
    room_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Pydantic schema for Photos
class PhotoBase(BaseModel):
    """
    Base schema for photo data.

    Attributes:
        url (str): Photo URL.
    """
    url: str

class PhotoCreate(PhotoBase):
    """Schema for creating a new photo."""
    pass    

class PhotoResponse(PhotoBase):
    """
    Schema for photo response.

    Attributes:
        id (int): Photo ID.
        observation_id (int): Observation ID.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    id: int
    observation_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Pydantic schema for Observations
class ObservationBase(BaseModel):
    """
    Base schema for observation data.

    Attributes:
        content (str): Observation content.
        user_id (int): User ID (observer).
        potentialvio (bool): Whether it's a potential violation.
        photos (list[PhotoCreate]): List of photos to create.
        codes (list[int]): List of suspected code IDs.
    """
    content: str
    user_id: int
    potentialvio: Optional[bool] = False
    photos: Optional[List[PhotoCreate]] = None
    codes: Optional[List[int]] = None  # suspected code IDs

class ObservationCreate(ObservationBase):
    """Schema for creating a new observation."""
    pass

class ObservationResponse(ObservationBase):
    """
    Schema for observation response.

    Attributes:
        id (int): Observation ID.
        area_id (int): Area ID.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        codes (list[CodeResponse]): Suspected codes.
        photos (list[PhotoResponse]): Photos.
    """
    id: int
    content: str
    area_id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    codes: Optional[List['CodeResponse']] = None
    photos: Optional[List[PhotoResponse]] = None

    class Config:
        from_attributes = True

class ObservationUpdate(BaseModel):
    """
    Schema for updating an observation.

    Attributes:
        content (str): Content.
        potentialvio (bool): Potential violation status.
        codes (list[int]): List of code IDs.
    """
    content: Optional[str] = None
    potentialvio: Optional[bool] = None
    codes: Optional[List[int]] = None

# Observation + Area/Unit context for review screens
class PotentialObservationResponse(BaseModel):
    """
    Extended observation response with context for review screens.

    Attributes:
        id (int): Observation ID.
        content (str): Content.
        area_id (int): Area ID.
        user_id (int): User ID.
        potentialvio (bool): Potential violation status.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        inspection_id (int): Inspection ID.
        area_name (str): Area name.
        unit_id (int): Unit ID.
        unit_number (str): Unit number.
        codes (list[CodeResponse]): Suspected codes.
        photos (list[PhotoResponse]): Photos.
    """
    id: int
    content: str
    area_id: int
    user_id: int
    potentialvio: Optional[bool] = False
    created_at: datetime
    updated_at: datetime
    # Context
    inspection_id: int
    area_name: Optional[str] = None
    unit_id: Optional[int] = None
    unit_number: Optional[str] = None
    codes: Optional[List['CodeResponse']] = None
    photos: Optional[List[PhotoResponse]] = None

    class Config:
        from_attributes = True

# ViolationComment schemas
class ViolationCommentBase(BaseModel):
    """
    Base schema for violation comment data.

    Attributes:
        content (str): Comment content.
        user_id (int): User ID.
        violation_id (int): Violation ID.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
    """
    content: str
    user_id: int
    violation_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ViolationCommentCreate(ViolationCommentBase):
    """Schema for creating a new violation comment."""
    pass

class ViolationCommentResponse(ViolationCommentBase):
    """
    Schema for violation comment response.

    Attributes:
        id (int): Comment ID.
        user (UserResponse): User details.
    """
    id: int
    user: Optional[UserResponse] = None
    class Config:
        from_attributes = True

# Notifications
class NotificationBase(BaseModel):
    """
    Base schema for notification data.

    Attributes:
        title (str): Notification title.
        body (str): Notification body.
        inspection_id (int): Inspection ID (optional).
        comment_id (int): Comment ID (optional).
        user_id (int): User ID.
        read (bool): Read status.
    """
    title: Optional[str] = None
    body: Optional[str] = None
    inspection_id: Optional[int] = None
    comment_id: Optional[int] = None
    user_id: int
    read: Optional[bool] = False

class NotificationCreate(NotificationBase):
    """Schema for creating a new notification."""
    pass

class NotificationResponse(NotificationBase):
    """
    Schema for notification response.

    Attributes:
        id (int): Notification ID.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Update timestamp.
        origin_type (str): Type of origin for deep links.
        origin_label (str): Label for origin.
        origin_url_path (str): URL path for deep links.
    """
    id: int
    created_at: datetime
    updated_at: datetime
    # Computed origin info for client deep-links
    origin_type: Optional[str] = None  # e.g., 'inspection', 'address_comment', 'contact_comment'
    origin_label: Optional[str] = None  # e.g., '123 MAIN ST (Unit 2)' or contact name
    origin_url_path: Optional[str] = None  # e.g., '/address/123' or '/address/123/unit/45' or '/contacts/77' or '/inspection/5'

    class Config:
        from_attributes = True


# Resolve forward references for any cross-referenced schemas (helps Pydantic resolve string annotations)
try:
    ViolationResponse.update_forward_refs()
    CodeResponse.update_forward_refs()
    UnitResponse.update_forward_refs()
    ViolationCommentResponse.update_forward_refs()
    CommentResponse.update_forward_refs()
except Exception:
    # If any models are not yet defined at import time, it's okay — Pydantic will resolve when used.
    pass
