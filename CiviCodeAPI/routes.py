from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from models import Address
from schemas import AddressCreate, AddressResponse
from database import get_db  # Assuming a get_db function is set up to provide the database session

# Create a router instance
router = APIRouter()

# Get all addresses with optional pagination
@router.get("/addresses/", response_model=List[AddressResponse])
def get_addresses(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    addresses = db.query(Address).order_by(Address.id).offset(skip).limit(limit).all()
    return addresses

# Get a single address by ID
@router.get("/addresses/{address_id}", response_model=AddressResponse)
def get_address(address_id: int, db: Session = Depends(get_db)):
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    return address

# Create a new address
@router.post("/addresses/", response_model=AddressResponse)
def create_address(address: AddressCreate, db: Session = Depends(get_db)):
    new_address = Address(**address.dict())
    db.add(new_address)
    db.commit()
    db.refresh(new_address)
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
    return existing_address

# Delete an address
@router.delete("/addresses/{address_id}", response_model=AddressResponse)
def delete_address(address_id: int, db: Session = Depends(get_db)):
    address = db.query
