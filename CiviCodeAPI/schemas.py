from pydantic import BaseModel, validator, Field
from typing import Optional, List
from datetime import datetime, date
from constants import DEADLINE_OPTIONS, DEADLINE_VALUES

# Ensure CodeResponse is defined before ViolationResponse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schemas import CodeResponse

# Vacant property registration (annual)
class VacantRegistrationBase(BaseModel):
    registration_year: Optional[int] = None
    status: Optional[str] = None
    fee_amount: Optional[float] = 0.0
    fee_paid: Optional[bool] = False
    fee_paid_at: Optional[datetime] = None
    fire_damage: Optional[bool] = False
    registered_on: Optional[date] = None
    expires_on: Optional[date] = None
    maintenance_status: Optional[str] = None
    maintenance_notes: Optional[str] = None
    security_status: Optional[str] = None
    security_notes: Optional[str] = None
    compliance_checked_at: Optional[datetime] = None
    notes: Optional[str] = None


class VacantRegistrationCreate(VacantRegistrationBase):
    pass


class VacantRegistrationUpdate(BaseModel):
    registration_year: Optional[int] = None
    status: Optional[str] = None
    fee_amount: Optional[float] = None
    fee_paid: Optional[bool] = None
    fee_paid_at: Optional[datetime] = None
    fire_damage: Optional[bool] = None
    registered_on: Optional[date] = None
    expires_on: Optional[date] = None
    maintenance_status: Optional[str] = None
    maintenance_notes: Optional[str] = None
    security_status: Optional[str] = None
    security_notes: Optional[str] = None
    compliance_checked_at: Optional[datetime] = None
    notes: Optional[str] = None


class VacantRegistrationResponse(VacantRegistrationBase):
    id: int
    address_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Pydantic schema for address
class AddressCreate(BaseModel):
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
    id: int
    combadd: Optional[str] = None
    ownername: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    vacant_registrations: List[VacantRegistrationResponse] = Field(default_factory=list)
    current_vacant_registration: Optional[VacantRegistrationResponse] = None

    class Config:
        from_attributes = True


class SDATRefreshRequest(BaseModel):
    county: Optional[str] = None
    district: Optional[str] = None
    account_number: Optional[str] = None


class SDATRefreshResponse(BaseModel):
    address: AddressResponse
    updated_fields: List[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    mailing_lines: List[str] = Field(default_factory=list)


# Pydantic schema for User
class UserBase(BaseModel):
    email: str
    name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[int] = 0
    active: Optional[bool] = True

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    name: Optional[str] = None
    email: str
    created_at: datetime
    updated_at: datetime
    active: bool = True

    class Config:
        from_attributes = True

class UserUpdate(UserBase):
    password: Optional[str] = None

class PasswordResetRequest(BaseModel):
    email: str

class PasswordResetConfirm(BaseModel):
    token: str
    password: str

# Pydantic schema for Business
class BusinessBase(BaseModel):
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
    pass

class BusinessResponse(BusinessBase):
    id: int
    address_id: int
    address: Optional[AddressResponse] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Pydantic schema for Contact
class ContactBase(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = ""
    hidden: Optional[bool] = False

class ContactCreate(ContactBase):
    pass

class ContactResponse(ContactBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InspectionSummary(BaseModel):
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
    id: int
    inspection_id: int
    permit_type: Optional[str] = None
    permit_number: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContactDetailResponse(ContactResponse):
    addresses: List[AddressResponse] = Field(default_factory=list)
    businesses: List[BusinessResponse] = Field(default_factory=list)
    inspections: List[InspectionSummary] = Field(default_factory=list)
    permits: List[PermitSummary] = Field(default_factory=list)
    complaints: List[InspectionSummary] = Field(default_factory=list)

# Pydantic schema for Violations
class ViolationBase(BaseModel):
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
    codes: Optional[List[int]] = None  # Accept a list of code IDs when creating


class ViolationFromCommentRequest(BaseModel):
    """Payload for drafting a violation from an existing comment."""

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


class AttachmentCodeUpdate(BaseModel):
    code_ids: List[int] = Field(default_factory=list)


class ViolationResponse(ViolationBase):
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
    content: str
    user_id: int
    address_id: int  # Address ID is required
    unit_id: Optional[int] = None  # Unit ID is optional
    review_later: bool = False

# Schema for creating a new comment (doesn't include id, created_at, updated_at)
class CommentCreate(CommentBase):
    pass  # Inherit all fields from CommentBase for creation

class CommentReviewUpdate(BaseModel):
    review_later: bool

# Schema for returning comment data in API responses
class CommentResponse(CommentBase):
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
    results: List[CommentResponse]
    total: int
    page: int
    page_size: int
    has_more: bool

# Pydantic schema for Citations
class CitationBase(BaseModel):
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
    pass

class CitationResponse(BaseModel):
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
    address_id: int
    contact_id: Optional[int] = None
    status: Optional[int] = None
    source: str
    unit_id: Optional[int] = None
    business_id: Optional[int] = None
    description: Optional[str] = None
    channel: Optional[str] = None
    reported_violation_type: Optional[str] = None
    violation_subtype: Optional[str] = None
    severity: Optional[str] = None
    is_imminent_threat: Optional[bool] = False
    duplicate_of_id: Optional[int] = None

class InspectionCreate(InspectionBase):
    pass

class InspectionResponse(BaseModel):
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
    channel: Optional[str] = None
    reported_violation_type: Optional[str] = None
    violation_subtype: Optional[str] = None
    severity: Optional[str] = None
    is_imminent_threat: Optional[bool] = False
    duplicate_of_id: Optional[int] = None
    contact: Optional[ContactResponse] = None
    created_at: datetime
    updated_at: datetime
    status_message: Optional[str] = None  # ephemeral message about side-effects (e.g., license creation)

    class Config:
        from_attributes = True

class InspectionTriageUpdate(BaseModel):
    violation_subtype: Optional[str] = None
    severity: Optional[str] = None
    is_imminent_threat: Optional[bool] = None
    duplicate_of_id: Optional[int] = None

# --- Inspection comment schemas ---
class InspectionCommentBase(BaseModel):
    content: str
    user_id: int


class InspectionCommentCreate(InspectionCommentBase):
    pass


class InspectionCommentResponse(InspectionCommentBase):
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
    chapter: str
    section: str
    name: str
    description: str

class CodeCreate(CodeBase):
    pass

class CodeViolationSummary(BaseModel):
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
    id: int
    name: str
    chapter: str
    section: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CodeResponse(CodePublic):
    violation_count: int = 0
    violations: Optional[List[CodeViolationSummary]] = None

# Licenses
class LicenseBase(BaseModel):
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
    address_id: Optional[int] = None

class LicenseResponse(LicenseBase):
    inspection_id: int
    id: int
    created_at: datetime
    updated_at: datetime
    address_id: Optional[int] = None
    combadd: Optional[str] = None  # address combined

    class Config:
        from_attributes = True

class LicenseUpdate(BaseModel):
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
    inspection_id: int
    permit_type: Optional[str] = None
    business_id: Optional[int] = None
    permit_number: Optional[str] = None
    date_issued: Optional[date] = None
    expiration_date: Optional[date] = None
    conditions: Optional[str] = None
    paid: bool = False

class PermitCreate(PermitBase):
    pass

class PermitResponse(PermitBase):
    id: int
    created_at: datetime
    updated_at: datetime
    address_id: Optional[int] = None
    combadd: Optional[str] = None

    class Config:
        from_attributes = True


class PermitUpdate(BaseModel):
    permit_type: Optional[str] = None
    business_id: Optional[int] = None
    permit_number: Optional[str] = None
    date_issued: Optional[date] = None
    expiration_date: Optional[date] = None
    conditions: Optional[str] = None
    paid: Optional[bool] = None


class RecentActivityResponse(BaseModel):
    comments: List[CommentResponse]
    inspections: List[InspectionResponse]
    complaints: List[InspectionResponse]
    licenses: List[LicenseResponse]
    permits: List[PermitResponse]
    violations: List[ViolationResponse]


class OasDashboardResponse(BaseModel):
    pending_complaints: List[InspectionResponse]
    active_violations: List[ViolationResponse]
    active_violations_count: int = 0
    licenses_needing_action_count: int = 0
    licenses_not_paid: List[LicenseResponse]
    licenses_not_sent: List[LicenseResponse]


# Pydantic schema for ContactComments
class ContactCommentBase(BaseModel):
    contact_id: int
    comment: str
    user_id: int

class ContactCommentCreate(ContactCommentBase):
    pass

class ContactCommentResponse(ContactCommentBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Pydantic schema for Areas
class AreaBase(BaseModel):
    name: str
    notes: Optional[str] = None
    photos: Optional[List[str]] = None

class AreaCreate(AreaBase):
    unit_id: Optional[int] = None

class AreaResponse(AreaBase):
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
    number: str

class UnitCreate(UnitBase):
    pass

class UnitResponse(UnitBase):
    id: int
    number: str
    address_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Response schema for per-unit aggregated alert counts
class UnitAlertCountsResponse(BaseModel):
    unit_id: int
    unit_number: Optional[str] = None
    pending_inspections: int = 0
    open_violations: int = 0
    unpaid_citations: int = 0

    class Config:
        from_attributes = True

# Pydantic schema for Rooms
class RoomBase(BaseModel):
    name: str
    
class RoomCreate(RoomBase):
    pass

class RoomResponse(RoomBase):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Pydantic schema for Prompts
class PromptBase(BaseModel):
    content: str

class PromptCreate(PromptBase):
    pass

class PromptResponse(PromptBase):
    id: int
    content: str
    room_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Pydantic schema for Photos
class PhotoBase(BaseModel):
    url: str

class PhotoCreate(PhotoBase):
    pass    

class PhotoResponse(PhotoBase):
    id: int
    observation_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Pydantic schema for Observations
class ObservationBase(BaseModel):
    content: str
    user_id: int
    potentialvio: Optional[bool] = False
    photos: Optional[List[PhotoCreate]] = None
    codes: Optional[List[int]] = None  # suspected code IDs

class ObservationCreate(ObservationBase):
    pass

class ObservationResponse(ObservationBase):
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
    content: Optional[str] = None
    potentialvio: Optional[bool] = None
    codes: Optional[List[int]] = None

# Observation + Area/Unit context for review screens
class PotentialObservationResponse(BaseModel):
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
    content: str
    user_id: int
    violation_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ViolationCommentCreate(ViolationCommentBase):
    pass

class ViolationCommentResponse(ViolationCommentBase):
    id: int
    user: Optional[UserResponse] = None
    class Config:
        from_attributes = True

# Notifications
class NotificationBase(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    inspection_id: Optional[int] = None
    comment_id: Optional[int] = None
    user_id: int
    read: Optional[bool] = False

class NotificationCreate(NotificationBase):
    pass

class NotificationResponse(NotificationBase):
    id: int
    created_at: datetime
    updated_at: datetime
    # Computed origin info for client deep-links
    origin_type: Optional[str] = None  # e.g., 'inspection', 'address_comment', 'contact_comment'
    origin_label: Optional[str] = None  # e.g., '123 MAIN ST (Unit 2)' or contact name
    origin_url_path: Optional[str] = None  # e.g., '/address/123' or '/address/123/unit/45' or '/contacts/77' or '/inspection/5'

    class Config:
        from_attributes = True


class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionBase(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys
    expiration_time: Optional[int] = None
    user_agent: Optional[str] = None


class PushSubscriptionResponse(BaseModel):
    id: int
    user_id: int
    endpoint: str
    expiration_time: Optional[int] = None
    user_agent: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PushSubscriptionCreate(PushSubscriptionBase):
    pass


class PushSubscriptionDelete(BaseModel):
    endpoint: str


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
