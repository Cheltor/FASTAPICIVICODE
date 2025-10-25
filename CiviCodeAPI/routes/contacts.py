
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from sqlalchemy.orm import Session, selectinload
from typing import List
from models import Contact, Inspection, Business
from schemas import ContactCreate, ContactResponse, ContactDetailResponse, InspectionSummary, PermitSummary
from database import get_db
from sqlalchemy import or_, func

router = APIRouter()




# Get all contacts, with optional search
@router.get("/contacts/", response_model=List[ContactResponse])
def get_contacts(
    skip: int = 0,
    search: str = Query(None, description="Search term for contact name, email, or phone"),
    db: Session = Depends(get_db)
):
    query = db.query(Contact)
    if search and search.strip():
        like = f"%{search}%"
        query = query.filter(
            or_(
                Contact.name.ilike(like),
                Contact.email.ilike(like),
                Contact.phone.ilike(like)
            )
        )
    contacts = query.order_by(Contact.created_at.desc()).offset(skip).all()
    return contacts

# Create a new contact
@router.post("/contacts/", response_model=ContactResponse)
def create_contact(contact: ContactCreate, db: Session = Depends(get_db)):
        name = (contact.name or '').strip()
        if name:
            name_conflict = (
                db.query(Contact)
                .filter(func.lower(Contact.name) == name.lower())
                .first()
            )
            if name_conflict:
                raise HTTPException(status_code=409, detail='Contact name already exists')

        # Normalize email and phone for comparison
        email = (contact.email or "").strip().lower()
        phone_digits = "".join([c for c in (contact.phone or "") if c.isdigit()])

        # Check for duplicates by email or phone
        q = db.query(Contact)
        if email:
            q = q.filter(Contact.email.ilike(email))
        existing = q.first() if email else None

        if not existing and phone_digits:
            # Compare only digits to avoid formatting differences
            # Fetch potential matches and compare stripped digits
            candidates = db.query(Contact).filter(Contact.phone.isnot(None)).all()
            for c in candidates:
                digits = "".join([ch for ch in (c.phone or "") if ch.isdigit()])
                if digits and digits == phone_digits:
                    existing = c
                    break

        if existing:
            raise HTTPException(status_code=409, detail="Contact with this email or phone already exists")

        new_contact = Contact(**contact.dict())
        db.add(new_contact)
        db.commit()
        db.refresh(new_contact)
        return new_contact

# Get a specific contact by ID
@router.get("/contacts/search", response_model=List[ContactResponse])
def search_contacts(
    query: str = Query("", description="Search term for contact name, email, or phone"),
    limit: int = Query(5, ge=1, le=50, description="Limit the number of results"),
    db: Session = Depends(get_db),
):
    search_term = (query or "").strip()
    like_pattern = f"%{search_term}%"
    filters = [
        Contact.name.ilike(like_pattern),
        Contact.email.ilike(like_pattern),
    ]
    if search_term:
        filters.append(Contact.phone.ilike(like_pattern))

    base_results = (
        db.query(Contact)
        .filter(or_(*filters))
        .order_by(Contact.created_at.desc())
        .limit(limit * 3)
        .all()
    )

    digits = "".join(ch for ch in search_term if ch.isdigit())
    digit_results = []
    if digits:
        phone_digits_expr = func.coalesce(Contact.phone, "")
        for ch in ("-", " ", "(", ")", ".", "+"):
            phone_digits_expr = func.replace(phone_digits_expr, ch, "")
        digit_results = (
            db.query(Contact)
            .filter(phone_digits_expr.ilike(f"%{digits}%"))
            .order_by(Contact.created_at.desc())
            .limit(limit * 3)
            .all()
        )

    combined = []
    seen_ids = set()
    for contact in digit_results + base_results:
        if not contact or contact.id in seen_ids:
            continue
        seen_ids.add(contact.id)
        combined.append(contact)
        if len(combined) >= limit:
            break

    return combined

# Get a specific contact by ID
@router.get("/contacts/{contact_id}", response_model=ContactDetailResponse)
def get_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = (
        db.query(Contact)
        .options(
            selectinload(Contact.addresses),
            selectinload(Contact.businesses).selectinload(Business.address),
            selectinload(Contact.inspections).selectinload(Inspection.address),
            selectinload(Contact.inspections).selectinload(Inspection.permits),
        )
        .filter(Contact.id == contact_id)
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    contact_data = ContactDetailResponse.model_validate(contact, from_attributes=True)
    contact_data.inspections = [
        InspectionSummary.model_validate(inspection, from_attributes=True)
        for inspection in contact.inspections
        if (inspection.source or '').lower() != 'complaint'
    ]
    contact_data.complaints = [
        InspectionSummary.model_validate(inspection, from_attributes=True)
        for inspection in contact.inspections
        if (inspection.source or '').lower() == 'complaint'
    ]
    permit_map = {}
    for inspection in contact.inspections:
        for permit in (getattr(inspection, 'permits', None) or []):
            permit_map[permit.id] = permit
    contact_data.permits = [
        PermitSummary.model_validate(permit, from_attributes=True)
        for permit in permit_map.values()
    ]
    return contact_data
# Update an existing contact
@router.put("/contacts/{contact_id}", response_model=ContactResponse)
def update_contact(contact_id: int, contact: ContactCreate = Body(...), db: Session = Depends(get_db)):
    db_contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not db_contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    data = contact.dict()
    name_value = data.get('name')
    if name_value not in (None, ''):
        trimmed = str(name_value).strip()
        if trimmed:
            conflict = (
                db.query(Contact)
                .filter(func.lower(Contact.name) == trimmed.lower(), Contact.id != contact_id)
                .first()
            )
            if conflict:
                raise HTTPException(status_code=409, detail='Contact name already exists')
            data['name'] = trimmed
        else:
            data['name'] = ''

    for field, value in data.items():
        setattr(db_contact, field, value)
    db.commit()
    db.refresh(db_contact)
    return db_contact

# Delete a contact by ID
@router.delete("/contacts/{contact_id}", status_code=204)
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    try:
        db.delete(contact)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Unable to delete contact due to related records")


