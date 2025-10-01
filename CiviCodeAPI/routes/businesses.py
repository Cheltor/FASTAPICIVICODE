from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import date
from sqlalchemy.orm import Session, joinedload
from typing import List
from models import Business, Contact, BusinessContact
from sqlalchemy import or_
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
        q = q.filter(or_(Business.name.ilike(like), Business.trading_as.ilike(like)))
    businesses = q.order_by(Business.name.asc()).limit(limit).all()
    return businesses

# Get all businesses
@router.get("/businesses/", response_model=List[BusinessResponse])
def get_businesses(skip: int = 0, db: Session = Depends(get_db)):
    businesses = db.query(Business).options(joinedload(Business.address)).offset(skip).all()

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