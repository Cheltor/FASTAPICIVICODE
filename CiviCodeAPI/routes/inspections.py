from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from models import Inspection
from schemas import InspectionCreate, InspectionResponse
from database import get_db

router = APIRouter()

# Get all inspections
@router.get("/inspections/", response_model=List[InspectionResponse])
def get_inspections(skip: int = 0, db: Session = Depends(get_db)):
  inspections = db.query(Inspection).offset(skip).all()
  return inspections

# Create a new inspection
@router.post("/inspections/", response_model=InspectionResponse)
def create_inspection(inspection: InspectionCreate, db: Session = Depends(get_db)):
    new_inspection = Inspection(**inspection.dict())
    db.add(new_inspection)
    db.commit()
    db.refresh(new_inspection)
    return new_inspection

# Get a specific inspection by ID
@router.get("/inspections/{inspection_id}", response_model=InspectionResponse)
def get_inspection(inspection_id: int, db: Session = Depends(get_db)):
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return inspection

# Get all inspections for a specific Address
@router.get("/inspections/address/{address_id}", response_model=List[InspectionResponse])
def get_inspections_by_address(address_id: int, db: Session = Depends(get_db)):
    inspections = db.query(Inspection).filter(Inspection.address_id == address_id).all()
    return inspections
    