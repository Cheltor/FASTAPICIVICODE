from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from models import Business
from schemas import BusinessCreate, BusinessResponse
from database import get_db

router = APIRouter()

# Get all businesses
@router.get("/businesses/", response_model=List[BusinessResponse])
def get_businesses(skip: int = 0, db: Session = Depends(get_db)):
    businesses = db.query(Business).offset(skip).all()
    return businesses

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
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business