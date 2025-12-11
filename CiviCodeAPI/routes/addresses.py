
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from sqlalchemy import or_, func
from sqlalchemy.exc import IntegrityError
from datetime import datetime, date, timedelta
from storage import blob_service_client, CONTAINER_NAME
from media_service import ensure_blob_browser_safe
from database import get_db  # Ensure get_db is imported before use
from urllib.parse import quote
from models import Address, Comment, Violation, Inspection, Unit, Citation, ActiveStorageAttachment, ActiveStorageBlob, Contact, AddressContact, User, VacantRegistration
import models
from schemas import (
    AddressCreate,
    AddressResponse,
    CommentResponse,
    ViolationResponse,
    InspectionResponse,
    ViolationCreate,
    CommentCreate,
    InspectionCreate,
    UnitResponse,
    UnitCreate,
    ContactResponse,
    ContactCreate,
    SDATRefreshRequest,
    SDATRefreshResponse,
    VacantRegistrationCreate,
    VacantRegistrationResponse,
    VacantRegistrationUpdate,
)

import schemas

from sdat_client import fetch_owner_info

router = APIRouter()

# Admin-only guard for edits/deletes
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")
SECRET_KEY = "trpdds2020"
ALGORITHM = "HS256"

def _require_admin(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        import jwt
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid auth token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if int(getattr(user, 'role', 0)) < 3:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

ACTIVE_REGISTRATION_STATUSES = {"pending", "active", "waived"}


def _resolve_value(data: dict, key: str, existing, default=None):
    if key in data:
        return data[key]
    if existing is not None:
        return getattr(existing, key, default)
    return default


def _normalize_registration_payload(data: dict, existing: Optional[VacantRegistration] = None) -> dict:
    today = date.today()
    status_value = _resolve_value(data, "status", existing, "pending")
    status = status_value.strip() if isinstance(status_value, str) else status_value
    status = status or "pending"

    registered_on = _resolve_value(data, "registered_on", existing, None)
    if registered_on is None and status != "draft":
        registered_on = today

    registration_year = _resolve_value(data, "registration_year", existing, None)
    if registration_year is None:
        registration_year = registered_on.year if registered_on else today.year

    expires_on = _resolve_value(data, "expires_on", existing, None)
    if expires_on is None and registered_on:
        expires_on = registered_on + timedelta(days=365)

    fee_paid = bool(_resolve_value(data, "fee_paid", existing, False))
    fee_paid_at = _resolve_value(data, "fee_paid_at", existing, None)
    if fee_paid and fee_paid_at is None:
        fee_paid_at = datetime.utcnow()
    if fee_paid_at and not fee_paid:
        fee_paid = True

    fee_amount = _resolve_value(data, "fee_amount", existing, 0.0)
    if fee_amount is None:
        fee_amount = 0.0

    fire_damage = bool(_resolve_value(data, "fire_damage", existing, False))
    maintenance_status = _resolve_value(data, "maintenance_status", existing, None)
    maintenance_notes = _resolve_value(data, "maintenance_notes", existing, None)
    security_status = _resolve_value(data, "security_status", existing, None)
    security_notes = _resolve_value(data, "security_notes", existing, None)
    compliance_checked_at = _resolve_value(data, "compliance_checked_at", existing, None)
    notes = _resolve_value(data, "notes", existing, None)

    if expires_on and expires_on < today:
        status = "expired"

    return {
        "registration_year": registration_year,
        "status": status,
        "fee_amount": fee_amount,
        "fee_paid": fee_paid,
        "fee_paid_at": fee_paid_at,
        "fire_damage": fire_damage,
        "registered_on": registered_on,
        "expires_on": expires_on,
        "maintenance_status": maintenance_status,
        "maintenance_notes": maintenance_notes,
        "security_status": security_status,
        "security_notes": security_notes,
        "compliance_checked_at": compliance_checked_at,
        "notes": notes,
    }


def _sync_vacancy_status_for_registration(address: Address, registration: VacantRegistration):
    if not address or not registration:
        return
    today = date.today()
    if registration.expires_on and registration.expires_on < today:
        registration.status = "expired"
        if address.vacancy_status == "registered":
            address.vacancy_status = "vacant"
        return
    is_active = registration.status in ACTIVE_REGISTRATION_STATUSES and (
        registration.expires_on is None or registration.expires_on >= today
    )
    if is_active:
        address.vacancy_status = "registered"
    elif registration.status == "expired" and address.vacancy_status == "registered":
        address.vacancy_status = "vacant"


def _latest_vacant_registrations_by_address(db: Session, address_ids: List[int]) -> dict:
    if not address_ids:
        return {}
    rows = (
        db.query(VacantRegistration)
        .filter(VacantRegistration.address_id.in_(address_ids))
        .order_by(VacantRegistration.address_id, VacantRegistration.registration_year.desc(), VacantRegistration.created_at.desc())
        .all()
    )
    latest = {}
    for reg in rows:
        if reg.address_id not in latest:
            latest[reg.address_id] = reg
    return latest

# Get all contacts for an address
@router.get("/addresses/{address_id}/contacts", response_model=List[ContactResponse])
def get_address_contacts(address_id: int, db: Session = Depends(get_db)):
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    return address.contacts

# Add a contact (existing or new) to an address
@router.post("/addresses/{address_id}/contacts", response_model=List[ContactResponse])
def add_address_contact(address_id: int, contact: dict = Body(...), db: Session = Depends(get_db)):
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    contact_id = contact.get("contact_id")
    if contact_id:
        # Add existing contact
        contact_obj = db.query(Contact).filter(Contact.id == contact_id).first()
        if not contact_obj:
            raise HTTPException(status_code=404, detail="Contact not found")
    else:
        # Create new contact
        contact_obj = Contact(
            name=contact.get("name"),
            email=contact.get("email"),
            phone=contact.get("phone")
        )
        db.add(contact_obj)
        db.commit()
        db.refresh(contact_obj)
    # Check for existing association
    assoc = db.query(AddressContact).filter_by(address_id=address_id, contact_id=contact_obj.id).first()
    if not assoc:
        assoc = AddressContact(address_id=address_id, contact_id=contact_obj.id)
        db.add(assoc)
        db.commit()
    # Return updated list
    address = db.query(Address).filter(Address.id == address_id).first()
    return address.contacts


# Remove a contact from an address
@router.delete("/addresses/{address_id}/contacts/{contact_id}", response_model=List[ContactResponse])
def remove_address_contact(address_id: int, contact_id: int, db: Session = Depends(get_db)):
    assoc = db.query(AddressContact).filter_by(address_id=address_id, contact_id=contact_id).first()
    if not assoc:
        raise HTTPException(status_code=404, detail="Contact association not found")
    db.delete(assoc)
    db.commit()
    address = db.query(Address).filter(Address.id == address_id).first()
    return address.contacts

# Get all addresses
@router.get("/addresses/", response_model=List[AddressResponse])
def get_addresses(skip: int = 0, db: Session = Depends(get_db)):
    addresses = (
        db.query(Address)
        .order_by(Address.created_at.desc())
        .offset(skip)
        .all()
    )
    for addr in addresses:
        setattr(addr, "vacant_registrations", [])
        setattr(addr, "current_vacant_registration", None)
    return addresses

# Search for addresses by partial match of combadd, with a limit on results
@router.get("/addresses/search", response_model=List[AddressResponse])
def search_addresses(
    query: str = Query(..., description="Search term for address combadd or property name"),
    limit: int = Query(5, ge=1, le=50, description="Limit the number of results"),
    db: Session = Depends(get_db)
):
    # Perform a case-insensitive search on combadd or property_name using the query parameter
    addresses = (
        db.query(Address)
        .filter(
            or_(
                Address.combadd.ilike(f"%{query}%"),       # Search by address string
                Address.property_name.ilike(f"%{query}%"),  # Search by property name
                Address.aka.ilike(f"%{query}%"),            # Search by AKA
                Address.ownername.ilike(f"%{query}%")       # Search by owner name
            )
        )
        .limit(limit)
        .all()
    )
    return addresses


# Get addresses by vacancy status (for potentially vacant, registered, and vacant)
@router.get("/addresses/by-vacancy-status", response_model=List[AddressResponse])
def get_addresses_by_vacancy_status(db: Session = Depends(get_db)):
    addresses = db.query(Address).filter(Address.vacancy_status != "occupied").all()
    reg_map = _latest_vacant_registrations_by_address(db, [addr.id for addr in addresses])
    for addr in addresses:
        setattr(addr, "vacant_registrations", [])
        latest_reg = reg_map.get(addr.id)
        if latest_reg:
            _sync_vacancy_status_for_registration(addr, latest_reg)
            setattr(addr, "current_vacant_registration", latest_reg)
    return addresses

# Vacant property registration lifecycle (annual)
@router.get(
    "/addresses/{address_id}/vacant-registrations",
    response_model=List[VacantRegistrationResponse],
)
def list_vacant_registrations(address_id: int, db: Session = Depends(get_db)):
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    registrations = (
        db.query(VacantRegistration)
        .filter(VacantRegistration.address_id == address_id)
        .order_by(VacantRegistration.registration_year.desc(), VacantRegistration.created_at.desc())
        .all()
    )
    for reg in registrations:
        _sync_vacancy_status_for_registration(address, reg)
    return registrations


@router.post(
    "/addresses/{address_id}/vacant-registrations",
    response_model=VacantRegistrationResponse,
)
def create_vacant_registration(
    address_id: int,
    payload: VacantRegistrationCreate,
    db: Session = Depends(get_db),
):
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")

    data = _normalize_registration_payload(payload.dict(exclude_unset=True))
    registration = VacantRegistration(address_id=address_id, **data)
    db.add(registration)
    _sync_vacancy_status_for_registration(address, registration)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A registration for this year already exists for this address",
        )
    db.refresh(registration)
    return registration


@router.patch(
    "/addresses/{address_id}/vacant-registrations/{registration_id}",
    response_model=VacantRegistrationResponse,
)
def update_vacant_registration(
    address_id: int,
    registration_id: int,
    payload: VacantRegistrationUpdate,
    db: Session = Depends(get_db),
):
    registration = (
        db.query(VacantRegistration)
        .filter(VacantRegistration.id == registration_id, VacantRegistration.address_id == address_id)
        .first()
    )
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")

    data = _normalize_registration_payload(payload.dict(exclude_unset=True), existing=registration)
    for key, value in data.items():
        setattr(registration, key, value)

    _sync_vacancy_status_for_registration(registration.address, registration)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A registration for this year already exists for this address",
        )
    db.refresh(registration)
    return registration

# Get a single address by ID
@router.get("/addresses/{address_id}", response_model=AddressResponse)
def get_address(address_id: int, db: Session = Depends(get_db)):
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")

    registrations = (
        db.query(VacantRegistration)
        .filter(VacantRegistration.address_id == address_id)
        .order_by(VacantRegistration.registration_year.desc(), VacantRegistration.created_at.desc())
        .all()
    )
    for reg in registrations:
        _sync_vacancy_status_for_registration(address, reg)
    setattr(address, "vacant_registrations", registrations)
    setattr(address, "current_vacant_registration", registrations[0] if registrations else None)
    return address


def _normalize_string(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


@router.post(
    "/addresses/{address_id}/refresh-owner",
    response_model=SDATRefreshResponse,
)
def refresh_owner_from_sdat(
    address_id: int,
    payload: SDATRefreshRequest = Body(default=None),
    db: Session = Depends(get_db),
):
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")

    lookup = payload or SDATRefreshRequest()

    county = _normalize_string(lookup.county) or "17"
    district = (
        _normalize_string(lookup.district)
        or _normalize_string(getattr(address, "district", None))
    )
    account_number = (
        _normalize_string(lookup.account_number)
        or _normalize_string(getattr(address, "property_id", None))
        or _normalize_string(getattr(address, "pid", None))
    )

    if not account_number:
        raise HTTPException(
            status_code=400,
            detail="Missing SDAT account number. Provide account_number or populate property_id/pid on the address.",
        )

    try:
        owner_info = fetch_owner_info(
            county=county,
            account_number=account_number,
            district=district,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=500, detail="Unexpected SDAT lookup error") from exc

    if not owner_info.owner_name and not owner_info.mailing_lines:
        raise HTTPException(
            status_code=404,
            detail="SDAT response did not include owner information. Check the district and account number.",
        )

    updated_fields: List[str] = []

    def assign(field: str, value: Optional[str]):
        nonlocal updated_fields
        new_value = _normalize_string(value)
        if new_value is None:
            return
        current = getattr(address, field, None)
        current_norm = _normalize_string(current) if isinstance(current, str) else current
        if current_norm != new_value:
            setattr(address, field, new_value)
            updated_fields.append(field)

    assign("ownername", owner_info.owner_name)
    assign("owneraddress", owner_info.owner_address)
    assign("ownercity", owner_info.owner_city)
    assign("ownerstate", owner_info.owner_state)
    assign("ownerzip", owner_info.owner_zip)

    # Only populate identifiers if we have data and fields are blank.
    if not _normalize_string(getattr(address, "district", None)) and owner_info.rendered_district:
        assign("district", owner_info.rendered_district)
    if not _normalize_string(getattr(address, "property_id", None)) and owner_info.rendered_account:
        assign("property_id", owner_info.rendered_account)

    db.commit()
    db.refresh(address)

    return SDATRefreshResponse(
        address=address,
        updated_fields=updated_fields,
        source_url=owner_info.source_url,
        mailing_lines=owner_info.mailing_lines,
    )

# Create a new address
@router.post("/addresses/", response_model=AddressResponse)
def create_address(address: AddressCreate, db: Session = Depends(get_db)):
    new_address = Address(**address.dict())
    db.add(new_address)
    db.commit()
    db.refresh(new_address)
    setattr(new_address, "vacant_registrations", [])
    setattr(new_address, "current_vacant_registration", None)
    return new_address

# Update an existing address
@router.put("/addresses/{address_id}", response_model=AddressResponse)
def update_address(address_id: int, address: AddressCreate, db: Session = Depends(get_db)):
    existing_address = db.query(Address).filter(Address.id == address_id).first()
    if not existing_address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    for key, value in address.dict().items():
        setattr(existing_address, key, value)
    
    db.commit()
    db.refresh(existing_address)
    setattr(existing_address, "vacant_registrations", [])
    setattr(existing_address, "current_vacant_registration", None)
    return existing_address

# Delete an address (clean up dependents first)
@router.delete("/addresses/{address_id}", response_model=AddressResponse)
def delete_address(address_id: int, db: Session = Depends(get_db)):
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")

    try:
        # Remove address-contact associations
        db.query(AddressContact).filter(AddressContact.address_id == address_id).delete(synchronize_session=False)

        # Delete comments for this address
        db.query(Comment).filter(Comment.address_id == address_id).delete(synchronize_session=False)

        # Delete units under this address (unit has FK address_id)
        db.query(Unit).filter(Unit.address_id == address_id).delete(synchronize_session=False)

        # Delete violations tied to this address and their dependents
        from models import Violation as ViolationModel, Citation as CitationModel, ViolationComment as ViolationCommentModel, ViolationCode as ViolationCodeModel
        vio_ids = [row.id for row in db.query(ViolationModel.id).filter(ViolationModel.address_id == address_id).all()]
        if vio_ids:
            db.query(CitationModel).filter(CitationModel.violation_id.in_(vio_ids)).delete(synchronize_session=False)
            db.query(ViolationCommentModel).filter(ViolationCommentModel.violation_id.in_(vio_ids)).delete(synchronize_session=False)
            db.query(ViolationCodeModel).filter(ViolationCodeModel.violation_id.in_(vio_ids)).delete(synchronize_session=False)
            db.query(ViolationModel).filter(ViolationModel.id.in_(vio_ids)).delete(synchronize_session=False)

        # Delete inspections tied to this address and their dependents
        from models import Inspection as InspectionModel
        insp_ids = [row.id for row in db.query(InspectionModel.id).filter(InspectionModel.address_id == address_id).all()]
        if insp_ids:
            from models import License as LicenseModel, Permit as PermitModel, Notification as NotificationModel
            from models import InspectionComment as InspectionCommentModel, InspectionCode as InspectionCodeModel, Area as AreaModel, Observation as ObservationModel, Photo as PhotoModel
            # Delete child tables of inspections
            db.query(LicenseModel).filter(LicenseModel.inspection_id.in_(insp_ids)).delete(synchronize_session=False)
            db.query(PermitModel).filter(PermitModel.inspection_id.in_(insp_ids)).delete(synchronize_session=False)
            db.query(NotificationModel).filter(NotificationModel.inspection_id.in_(insp_ids)).delete(synchronize_session=False)
            db.query(InspectionCommentModel).filter(InspectionCommentModel.inspection_id.in_(insp_ids)).delete(synchronize_session=False)
            db.query(InspectionCodeModel).filter(InspectionCodeModel.inspection_id.in_(insp_ids)).delete(synchronize_session=False)

            # Areas under inspections -> observations -> photos
            area_ids = [row.id for row in db.query(AreaModel.id).filter(AreaModel.inspection_id.in_(insp_ids)).all()]
            if area_ids:
                obs_ids = [row.id for row in db.query(ObservationModel.id).filter(ObservationModel.area_id.in_(area_ids)).all()]
                if obs_ids:
                    db.query(PhotoModel).filter(PhotoModel.observation_id.in_(obs_ids)).delete(synchronize_session=False)
                    db.query(ObservationModel).filter(ObservationModel.id.in_(obs_ids)).delete(synchronize_session=False)
                db.query(AreaModel).filter(AreaModel.id.in_(area_ids)).delete(synchronize_session=False)

            # Delete the inspections themselves
            db.query(InspectionModel).filter(InspectionModel.id.in_(insp_ids)).delete(synchronize_session=False)

        # Finally, delete the address
        db.delete(address)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Unable to delete address due to related records")

    return address

# PATCH route to update only the vacancy_status of an address
@router.patch("/addresses/{address_id}/vacancy-status", response_model=AddressResponse)
def update_vacancy_status(address_id: int, data: dict = Body(...), db: Session = Depends(get_db)):
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    if "vacancy_status" not in data:
        raise HTTPException(status_code=400, detail="Missing vacancy_status")
    address.vacancy_status = data["vacancy_status"]
    db.commit()
    db.refresh(address)
    return address

@router.patch("/addresses/{address_id}/location")
def update_address_location(
    address_id: int,
    location: dict = Body(..., example={"latitude": 38.0, "longitude": -77.0}),
    db: Session = Depends(get_db)
):
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    if "latitude" in location:
        address.latitude = float(location["latitude"])
    if "longitude" in location:
        address.longitude = float(location["longitude"])
        
    db.commit()
    db.refresh(address)
    return {"message": "Location updated", "latitude": address.latitude, "longitude": address.longitude}

# Show the comments for the address
@router.get("/addresses/{address_id}/comments", response_model=List[CommentResponse])
def get_address_comments(address_id: int, db: Session = Depends(get_db)):
    # Query the comments for the given address ID and order by created_at descending
    comments = db.query(Comment).filter(Comment.address_id == address_id).order_by(Comment.created_at.desc()).all()
    if not comments:
        raise HTTPException(status_code=404, detail="No comments found for this address")
    return comments

# Add a comment to the address
@router.post("/addresses/{address_id}/comments", response_model=CommentResponse)
def create_comment_for_address(address_id: int, comment: CommentCreate, db: Session = Depends(get_db)):
    # Create and save the comment
    new_comment = Comment(address_id=address_id, **comment.dict())
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment

# Update a comment for the address
@router.put("/addresses/{address_id}/comments/{comment_id}", response_model=CommentResponse)
def update_address_comment(address_id: int, comment_id: int, comment: CommentResponse, db: Session = Depends(get_db), admin_user: User = Depends(_require_admin)):
    # Check if the address exists
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Check if the comment exists
    existing_comment = db.query(Comment).filter(Comment.id == comment_id, Comment.address_id == address_id).first()
    if not existing_comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Update the comment
    for key, value in comment.dict().items():
        setattr(existing_comment, key, value)
    
    db.commit()
    db.refresh(existing_comment)
    return existing_comment

# Delete a comment for the address
@router.delete("/addresses/{address_id}/comments/{comment_id}", response_model=CommentResponse)
def delete_address_comment(address_id: int, comment_id: int, db: Session = Depends(get_db), admin_user: User = Depends(_require_admin)):
    # Check if the address exists
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Check if the comment exists
    existing_comment = db.query(Comment).filter(Comment.id == comment_id, Comment.address_id == address_id).first()
    if not existing_comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Delete the comment
    db.delete(existing_comment)
    db.commit()
    return existing_comment

# Show the violations for the address
@router.get("/addresses/{address_id}/violations", response_model=List[ViolationResponse])
def get_address_violations(address_id: int, db: Session = Depends(get_db)):
    # Query violations that are either directly attached to the address OR attached to a Unit that belongs to the address.
    # Eager-load related Unit, Address and Codes so the response includes unit information without additional queries.
    violations_query = (
        db.query(Violation)
        .outerjoin(Unit, Violation.unit_id == Unit.id)
        .options(joinedload(Violation.unit), joinedload(Violation.codes), joinedload(Violation.address))
        .filter(or_(Violation.address_id == address_id, Unit.address_id == address_id))
        .order_by(Violation.created_at.desc())
    )

    violations = violations_query.all()
    if not violations:
        raise HTTPException(status_code=404, detail="No violations found for this address")

    # Build response dicts to include combadd, deadline_date, codes and unit info
    response = []
    for violation in violations:
        violation_dict = violation.__dict__.copy()
        violation_dict['combadd'] = violation.address.combadd if violation.address else None
        try:
            violation_dict['deadline_date'] = violation.deadline_date
        except Exception:
            violation_dict['deadline_date'] = None
        violation_dict['codes'] = violation.codes
        violation_dict['user'] = None
        if getattr(violation, 'user', None):
            violation_dict['user'] = violation.user
        # Include unit info if present
        violation_dict['unit'] = getattr(violation, 'unit', None)
        response.append(violation_dict)

    return response

# Add a violation to the address

@router.post("/addresses/{address_id}/violations", response_model=ViolationResponse)
def add_address_violation(address_id: int, violation: ViolationCreate, db: Session = Depends(get_db)):
    # Check if the address exists
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")

    violation_data = violation.dict(exclude={"codes"})
    violation_data["address_id"] = address_id
    if not violation_data.get("violation_type"):
        violation_data["violation_type"] = "doorhanger"
    if not violation_data.get("status"):
        violation_data["status"] = 0
    new_violation = Violation(**violation_data)
    db.add(new_violation)
    db.commit()
    # Associate codes if provided
    if violation.codes:
        codes = db.query(models.Code).filter(models.Code.id.in_(violation.codes)).all()
        new_violation.codes = codes
        db.commit()
    db.refresh(new_violation)
    return new_violation

# Update a violation for the address
@router.put("/addresses/{address_id}/violations/{violation_id}", response_model=ViolationResponse)
def update_address_violation(address_id: int, violation_id: int, violation: ViolationResponse, db: Session = Depends(get_db)):
    # Check if the address exists
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Check if the violation exists
    existing_violation = db.query(Violation).filter(Violation.id == violation_id, Violation.address_id == address_id).first()
    if not existing_violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    
    # Update the violation
    for key, value in violation.dict().items():
        setattr(existing_violation, key, value)
    
    db.commit()
    db.refresh(existing_violation)
    return existing_violation

# Delete a violation for the address
@router.delete("/addresses/{address_id}/violations/{violation_id}", response_model=ViolationResponse)
def delete_address_violation(address_id: int, violation_id: int, db: Session = Depends(get_db)):
    # Check if the address exists
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Check if the violation exists
    existing_violation = db.query(Violation).filter(Violation.id == violation_id, Violation.address_id == address_id).first()
    if not existing_violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    
    # Delete the violation
    db.delete(existing_violation)
    db.commit()
    return existing_violation

# Show the inspections for the address
@router.get("/addresses/{address_id}/inspections", response_model=List[InspectionResponse])
def get_address_inspections(address_id: int, db: Session = Depends(get_db)):
    # Query the inspections for the given address ID and order by created_at descending
    inspections = db.query(Inspection).filter(
        Inspection.address_id == address_id,
        Inspection.source != 'Complaint'
    ).order_by(Inspection.created_at.desc()).all()
    if not inspections:
        raise HTTPException(status_code=404, detail="No inspections found for this address")
    return inspections

# Add an inspection to the address
@router.post("/addresses/{address_id}/inspections", response_model=InspectionResponse)
def add_address_inspection(address_id: int, inspection: InspectionResponse, db: Session = Depends(get_db)):
    # Check if the address exists
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Create a new inspection
    new_inspection = Inspection(**inspection.dict(), address_id=address_id)
    db.add(new_inspection)
    db.commit()
    db.refresh(new_inspection)
    return new_inspection

# Update an inspection for the address
@router.put("/addresses/{address_id}/inspections/{inspection_id}", response_model=InspectionResponse)
def update_address_inspection(address_id: int, inspection_id: int, inspection: InspectionResponse, db: Session = Depends(get_db)):
    # Check if the address exists
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Check if the inspection exists
    existing_inspection = db.query(Inspection).filter(Inspection.id == inspection_id, Inspection.address_id == address_id).first()
    if not existing_inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    # Update the inspection
    for key, value in inspection.dict().items():
        setattr(existing_inspection, key, value)
    
    db.commit()
    db.refresh(existing_inspection)
    return existing_inspection

# Delete an inspection for the address
@router.delete("/addresses/{address_id}/inspections/{inspection_id}", response_model=InspectionResponse)
def delete_address_inspection(address_id: int, inspection_id: int, db: Session = Depends(get_db)):
    # Check if the address exists
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Check if the inspection exists
    existing_inspection = db.query(Inspection).filter(Inspection.id == inspection_id, Inspection.address_id == address_id).first()
    if not existing_inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    # Delete the inspection
    db.delete(existing_inspection)
    db.commit()
    return existing_inspection

# Show all the units for the address
@router.get("/addresses/{address_id}/units", response_model=List[UnitResponse])
def get_address_units(address_id: int, db: Session = Depends(get_db)):
    # Query the units for the given address ID and order by created_at descending
    units = db.query(Unit).filter(Unit.address_id == address_id).order_by(Unit.created_at.desc()).all()
    
    # Return the units (it will be an empty list if no units are found)
    return units  # No need to raise an exception; an empty list will be returned if no units exist

# Add a unit to the address
@router.post("/addresses/{address_id}/units", response_model=UnitResponse)
def create_unit(address_id: int, unit: UnitCreate, db: Session = Depends(get_db)):
    # Check if the address exists
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Normalize number: trim + uppercase to avoid case/spacing duplicates
    normalized_number = (unit.number or "").strip().upper()
    if not normalized_number:
        raise HTTPException(status_code=400, detail="Unit number is required")

    # Prevent duplicates even if DB constraint is missing (compare TRIM/UPPER)
    existing = db.query(Unit).filter(
        Unit.address_id == address_id,
        func.upper(func.trim(Unit.number)) == normalized_number
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Unit with this number already exists for this address")

    # Create a new unit with normalized number
    new_unit = Unit(number=normalized_number, address_id=address_id)
    try:
        db.add(new_unit)
        db.commit()
        db.refresh(new_unit)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Unit with this number already exists for this address")
    return new_unit

# Unit information
@router.get("/units/{unit_id}", response_model=UnitResponse)
def get_unit(unit_id: int, db: Session = Depends(get_db)):
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    return unit

# Get units by address ID
@router.get("/units", response_model=List[UnitResponse])
def get_units_by_address_id(address_id: int, db: Session = Depends(get_db)):
    units = db.query(Unit).filter(Unit.address_id == address_id).order_by(Unit.created_at.desc()).all()
    if not units:
        raise HTTPException(status_code=404, detail="No units found for this address")
    return units


# Return per-unit aggregated alert counts for an address to avoid many client-side requests
@router.get("/addresses/{address_id}/unit_alert_counts", response_model=List[schemas.UnitAlertCountsResponse])
def get_unit_alert_counts(address_id: int, db: Session = Depends(get_db)):
    # Ensure the address exists
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")

    units = db.query(Unit).filter(Unit.address_id == address_id).all()
    if not units:
        return []

    unit_ids = [u.id for u in units]

    # Open violations grouped by unit (status == 0 considered open/current)
    violation_rows = (
        db.query(Violation.unit_id, func.count(Violation.id))
        .filter(Violation.unit_id.in_(unit_ids), Violation.status == 0)
        .group_by(Violation.unit_id)
        .all()
    )
    violation_map = {row[0]: row[1] for row in violation_rows}

    # Pending inspections grouped by unit - approximate using keywords similar to frontend
    pending_keywords = ['%pending%', '%scheduled%', '%open%', '%in progress%', '%in-progress%', '%awaiting%', '%requested%', '%draft%']
    inspection_conditions = [Inspection.status == None]
    inspection_conditions += [Inspection.status.ilike(k) for k in pending_keywords]
    inspection_rows = (
        db.query(Inspection.unit_id, func.count(Inspection.id))
        .filter(Inspection.unit_id.in_(unit_ids), Inspection.source != 'Complaint', or_(*inspection_conditions))
        .group_by(Inspection.unit_id)
        .all()
    )
    inspection_map = {row[0]: row[1] for row in inspection_rows}

    # Unpaid citations grouped by unit (status == 0 or NULL considered unpaid)
    citation_rows = (
        db.query(Citation.unit_id, func.count(Citation.id))
        .filter(Citation.unit_id.in_(unit_ids), or_(Citation.status == 0, Citation.status == None))
        .group_by(Citation.unit_id)
        .all()
    )
    citation_map = {row[0]: row[1] for row in citation_rows}

    results = []
    for u in units:
        results.append({
            'unit_id': u.id,
            'unit_number': u.number,
            'pending_inspections': int(inspection_map.get(u.id, 0)),
            'open_violations': int(violation_map.get(u.id, 0)),
            'unpaid_citations': int(citation_map.get(u.id, 0)),
        })

    return results

# Get all photos from comments for a specific address
@router.get("/addresses/{address_id}/photos", response_model=List[dict])
def get_address_photos(address_id: int, db: Session = Depends(get_db)):
    # Query the comments for the given address ID
    comments = db.query(Comment).filter(Comment.address_id == address_id).all()
    if not comments:
        raise HTTPException(status_code=404, detail="No comments found for this address")

    # Collect all photo URLs from the comments
    photos = []
    for comment in comments:
        attachments = db.query(ActiveStorageAttachment).filter_by(
            record_id=comment.id, record_type='Comment', name='photos'
        ).all()
        for attachment in attachments:
            blob = db.query(ActiveStorageBlob).filter_by(id=attachment.blob_id).first()
            if blob:
                try:
                    blob = ensure_blob_browser_safe(db, blob)
                except Exception:
                    pass
                encoded_key = quote(blob.key or "", safe="/")
                url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{encoded_key}"
                poster_url = None
                if (blob.content_type or "").startswith("video/") and blob.key.lower().endswith('.mp4'):
                    base = blob.key[:-4]
                    encoded_poster = quote(f"{base}-poster.jpg", safe="/")
                    poster_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{encoded_poster}"
                photos.append({
                    "filename": blob.filename,
                    "content_type": blob.content_type,
                    "url": url,
                    "poster_url": poster_url,
                    "created_at": attachment.created_at.isoformat() if getattr(attachment, 'created_at', None) else None,
                })

    return photos

# PATCH route to update a unit number (ensure uniqueness)
@router.patch("/units/{unit_id}", response_model=UnitResponse)
def update_unit_number(unit_id: int, data: dict = Body(...), db: Session = Depends(get_db)):
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    new_number = data.get("number")
    if not new_number:
        raise HTTPException(status_code=400, detail="Missing unit number")
    normalized_number = (new_number or "").strip().upper()
    if not normalized_number:
        raise HTTPException(status_code=400, detail="Unit number is required")
    # Check for duplicate number for this address (exclude self)
    duplicate = db.query(Unit).filter(
        Unit.address_id == unit.address_id,
        func.upper(func.trim(Unit.number)) == normalized_number,
        Unit.id != unit_id
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail="Unit number already exists for this address.")
    unit.number = normalized_number
    db.commit()
    db.refresh(unit)
    return unit
