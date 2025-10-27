from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import date
import re
from sqlalchemy.orm import Session, joinedload
from typing import List
from models import Business, Contact, BusinessContact, Inspection, License, Permit
from sqlalchemy import or_, func
from schemas import BusinessCreate, BusinessResponse, AddressResponse, ContactResponse
from fastapi import Body
from database import get_db

router = APIRouter()

# Get all contacts for a business
@router.get("/businesses/{business_id}/contacts", response_model=List[ContactResponse])
def get_business_contacts(business_id: int, db: Session = Depends(get_db)):
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business.contacts

# Add a contact (existing or new) to a business
@router.post("/businesses/{business_id}/contacts", response_model=List[ContactResponse])
def add_business_contact(business_id: int, contact: dict = Body(...), db: Session = Depends(get_db)):
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
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
    assoc = db.query(BusinessContact).filter_by(business_id=business_id, contact_id=contact_obj.id).first()
    if not assoc:
        assoc = BusinessContact(business_id=business_id, contact_id=contact_obj.id)
        db.add(assoc)
        db.commit()
    # Return updated list
    business = db.query(Business).filter(Business.id == business_id).first()
    return business.contacts

# Remove a contact from a business
@router.delete("/businesses/{business_id}/contacts/{contact_id}", response_model=List[ContactResponse])
def remove_business_contact(business_id: int, contact_id: int, db: Session = Depends(get_db)):
    assoc = db.query(BusinessContact).filter_by(business_id=business_id, contact_id=contact_id).first()
    if not assoc:
        raise HTTPException(status_code=404, detail="Contact association not found")
    db.delete(assoc)
    db.commit()
    business = db.query(Business).filter(Business.id == business_id).first()
    return business.contacts

# Search businesses
@router.get("/businesses/search", response_model=List[BusinessResponse])
def search_businesses(
    query: str = Query("", description="Search term for business name or trading-as"),
    limit: int = Query(5, ge=1, le=50, description="Limit the number of results"),
    db: Session = Depends(get_db)
):
    q = db.query(Business).options(joinedload(Business.address))
    if query and query.strip():
        like = f"%{query}%"
        digits = re.sub(r"\D", "", query)
        filters = [
            Business.name.ilike(like),
            Business.trading_as.ilike(like),
            Business.email.ilike(like),
            Business.website.ilike(like),
        ]
        if digits:
            digits_like = f"%{digits}%"
            filters.append(Business.phone.ilike(digits_like))
        filters.append(Business.phone.ilike(like))
        q = q.filter(or_(*filters))
    businesses = q.order_by(Business.name.asc()).limit(limit).all()
    return businesses

# Get all businesses
@router.get("/businesses/", response_model=List[BusinessResponse])
def get_businesses(skip: int = 0, db: Session = Depends(get_db)):
    businesses = (
        db.query(Business)
        .options(joinedload(Business.address))
        .order_by(Business.created_at.desc())
        .offset(skip)
        .all()
    )

    business_responses = []
    for business in businesses:
        # Extract the address if it exists
        address_data = None
        if business.address:
            try:
                # Create AddressResponse from the SQLAlchemy model
                address_data = AddressResponse.from_orm(business.address)
            except Exception as e:
                print(f"Error creating AddressResponse for business '{business.name}': {e}")

        # Map the BusinessResponse
        try:
            business_response = BusinessResponse(
                id=business.id,
                name=business.name,
                phone=business.phone,
                email=business.email,
                website=business.website,
                trading_as=business.trading_as,
                is_closed=business.is_closed,
                opened_on=business.opened_on,
                employee_count=business.employee_count,
                address_id=business.address_id,  # Ensure address_id is included
                address=address_data,
                created_at=business.created_at,
                updated_at=business.updated_at
            )
            business_responses.append(business_response)
        except Exception as e:
            print(f"Error creating BusinessResponse for business '{business.name}': {e}")

    return business_responses




# Create a new business
@router.post("/businesses/", response_model=BusinessResponse)
def create_business(business: BusinessCreate, db: Session = Depends(get_db)):
    name = (business.name or '').strip()
    trading = (business.trading_as or '').strip()
    email = (business.email or '').strip()
    phone_digits = re.sub(r"\D", "", business.phone or '')

    duplicates = (
        db.query(Business)
        .filter(Business.address_id == business.address_id)
        .all()
    )

    name_lower = name.lower()
    trading_lower = trading.lower()
    email_lower = email.lower()

    for existing in duplicates:
        conflicts = []
        existing_name = (existing.name or '').strip().lower()
        existing_trading = (existing.trading_as or '').strip().lower()
        existing_email = (existing.email or '').strip().lower()
        existing_phone_digits = re.sub(r"\D", "", existing.phone or '')

        if name_lower and existing_name and existing_name == name_lower:
            conflicts.append('name')
        if trading_lower and existing_trading and existing_trading == trading_lower:
            conflicts.append('trading name')
        if email_lower and existing_email and existing_email == email_lower:
            conflicts.append('email')
        if phone_digits and existing_phone_digits and existing_phone_digits == phone_digits:
            conflicts.append('phone number')

        if conflicts:
            readable = ', '.join(conflicts)
            raise HTTPException(status_code=409, detail=f'Duplicate business detected for this address (matching {readable}).')

    if name:
        existing_global = (
            db.query(Business)
            .filter(func.lower(Business.name) == name.lower(), Business.address_id != business.address_id)
            .first()
        )
        if existing_global:
            raise HTTPException(status_code=409, detail='Business name already exists at another address')

    new_business = Business(**business.dict())
    db.add(new_business)
    db.commit()
    db.refresh(new_business)
    return new_business

# Get a specific business by ID
@router.get("/businesses/{business_id}", response_model=BusinessResponse)
def get_business(business_id: int, db: Session = Depends(get_db)):
    business = db.query(Business).options(joinedload(Business.address)).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business

# Update business fields (partial)
@router.patch("/businesses/{business_id}", response_model=BusinessResponse)
def update_business(business_id: int, data: dict = Body(...), db: Session = Depends(get_db)):
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    # Allowed keys to update
    allowed = {"name", "website", "email", "phone", "trading_as", "unit_id", "is_closed", "opened_on", "employee_count"}

    if 'name' in data and data['name'] not in (None, ''):
        trimmed_name = str(data['name']).strip()
        if trimmed_name:
            existing = (
                db.query(Business)
                .filter(func.lower(Business.name) == trimmed_name.lower(), Business.id != business_id)
                .first()
            )
            if existing:
                raise HTTPException(status_code=409, detail='Business name already exists')
            data['name'] = trimmed_name
        else:
            data['name'] = ''

    for key, value in data.items():
        if key not in allowed:
            continue
        if key == "opened_on":
            if value in (None, ""):
                setattr(business, key, None)
            else:
                # Accept ISO string or date
                parsed = value if isinstance(value, date) else date.fromisoformat(str(value))
                setattr(business, key, parsed)
        elif key == "employee_count":
            setattr(business, key, None if value in (None, "") else int(value))
        elif key == "is_closed":
            setattr(business, key, bool(value))
        else:
            setattr(business, key, value)

    db.commit()
    db.refresh(business)
    return business

# Delete a business by ID
@router.delete("/businesses/{business_id}", status_code=204)
def delete_business(business_id: int, db: Session = Depends(get_db)):
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    try:
        # Null out foreign keys on related records before deleting the business to avoid orphan references
        db.query(Inspection).filter(Inspection.business_id == business_id).update({Inspection.business_id: None}, synchronize_session=False)
        db.query(License).filter(License.business_id == business_id).update({License.business_id: None}, synchronize_session=False)
        db.query(Permit).filter(Permit.business_id == business_id).update({Permit.business_id: None}, synchronize_session=False)
        db.flush()
        db.delete(business)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Unable to delete business due to related records")