from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime, date
from constants import DEADLINE_OPTIONS, DEADLINE_VALUES

# Ensure CodeResponse is defined before ViolationResponse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schemas import CodeResponse

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

    class Config:
        from_attributes = True

# Pydantic schema for User
class UserBase(BaseModel):
    email: str
    name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[int] = 0

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    name: Optional[str] = None
    email: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserUpdate(UserBase):
    password: Optional[str] = None

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

class ViolationResponse(ViolationBase):
    id: int
    created_at: datetime
    updated_at: datetime
    combadd: Optional[str] = None
    deadline_date: Optional[datetime]  # Include the deadline date in the response
    codes: Optional[List['CodeResponse']] = None
    violation_comments: Optional[List['ViolationCommentResponse']] = None
    user: Optional[UserResponse] = None  # <-- Add this line

    class Config:
        from_attributes = True

# Pydantic schema for Comments
class CommentBase(BaseModel):
    content: str
    user_id: int
    address_id: int  # Address ID is required
    unit_id: Optional[int] = None  # Unit ID is optional

# Schema for creating a new comment (doesn't include id, created_at, updated_at)
class CommentCreate(CommentBase):
    pass  # Inherit all fields from CommentBase for creation

# Schema for returning comment data in API responses
class CommentResponse(CommentBase):
    id: int
    content: str
    user_id: int
    address_id: int
    user: UserResponse  # Include the user response here for returning full user data
    unit_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # This allows returning ORM models as dicts

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

# Pydantic schema for Codes
class CodeBase(BaseModel):
    chapter: str
    section: str
    name: str
    description: str

class CodeCreate(CodeBase):
    pass

class CodeResponse(CodeBase):
    id: int
    name: str
    chapter: str
    section: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Licenses
class LicenseBase(BaseModel):
    inspection_id: int
    sent: Optional[bool] = False
    paid: bool
    license_type: int
    business_id: Optional[int] = None
    date_issued: Optional[date] = None
    expiration_date: Optional[date] = None
    fiscal_year: Optional[str] = None

class LicenseCreate(LicenseBase):
    pass

class LicenseResponse(LicenseBase):
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