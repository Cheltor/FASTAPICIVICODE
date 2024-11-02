from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session, joinedload
from typing import List
from models import Business
from schemas import BusinessCreate, BusinessResponse, AddressResponse
from database import get_db

router = APIRouter()

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