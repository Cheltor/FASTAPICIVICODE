from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from models import Contact
from schemas import ContactCreate, ContactResponse
from database import get_db

router = APIRouter()

# Get all contacts
@router.get("/contacts/", response_model=List[ContactResponse])
def get_contacts(skip: int = 0, db: Session = Depends(get_db)):
    contacts = db.query(Contact).offset(skip).all()
    return contacts

# Create a new contact
@router.post("/contacts/", response_model=ContactResponse)
def create_contact(contact: ContactCreate, db: Session = Depends(get_db)):
    new_contact = Contact(**contact.dict())
    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)
    return new_contact

# Get a specific contact by ID
@router.get("/contacts/{contact_id}", response_model=ContactResponse)
def get_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact
