from pydantic import BaseModel
from typing import Optional
from datetime import datetime

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
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Pydantic schema for Business
class BusinessBase(BaseModel):
    name: Optional[str] = None
    address_id: int
    unit_id: Optional[int] = None
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    trading_as: Optional[str] = None

class BusinessCreate(BusinessBase):
    pass

class BusinessResponse(BusinessBase):
    id: int
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

class ViolationCreate(ViolationBase):
    pass

class ViolationResponse(ViolationBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Pydantic schema for Comments
class CommentBase(BaseModel):
    content: str
    address_id: int
    user_id: int
    unit_id: Optional[int]  # Unit ID is optional

# Schema for creating a new comment (doesn't include id, created_at, updated_at)
class CommentCreate(CommentBase):
    pass  # Inherit all fields from CommentBase for creation

# Schema for returning comment data in API responses
class CommentResponse(CommentBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # This allows returning ORM models as dicts

# Pydantic schema for Citations
class CitationBase(BaseModel):
    description: Optional[str] = None
    status: Optional[int] = None
    address_id: int
    user_id: int
    deadline: Optional[str] = None
    citation_type: Optional[str] = None
    extend: Optional[int] = 0
    unit_id: Optional[int] = None
    inspection_id: Optional[int] = None
    business_id: Optional[int] = None
    comment: Optional[str] = None

class CitationCreate(CitationBase):
    pass

class CitationResponse(BaseModel):
    id: int
    violation_id: int  # Link to the violation
    deadline: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Pydantic schema for Inspections
class InspectionBase(BaseModel):
    address_id: int
    user_id: int
    status: Optional[int] = None
    inspection_type: Optional[str] = None
    unit_id: Optional[int] = None
    business_id: Optional[int] = None
    comment: Optional[str] = None

class InspectionCreate(InspectionBase):
    pass

class InspectionResponse(BaseModel):
    id: int
    address_id: int
    inspector_id: Optional[int] = None
    status: Optional[str] = None
    inspection_type: Optional[str] = None
    unit_id: Optional[int] = None
    business_id: Optional[int] = None
    comment: Optional[str] = None
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

class CodeResponse(CodeBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Licenses
class LicenseBase(BaseModel):
    inspection_id: int
    sent: Optional[bool] = False
    paid: int
    license_type: int

class LicenseCreate(LicenseBase):
    pass

class LicenseResponse(LicenseBase):
    id: int
    created_at: datetime
    updated_at: datetime

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

