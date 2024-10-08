from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from models import Violation
from schemas import ViolationCreate, ViolationResponse
from database import get_db

router = APIRouter()

# Get all violations
@router.get("/violations/", response_model=List[ViolationResponse])
def get_violations(skip: int = 0, db: Session = Depends(get_db)):
    violations = db.query(Violation).offset(skip).all()
    return violations

# Create a new violation
@router.post("/violations/", response_model=ViolationResponse)
def create_violation(violation: ViolationCreate, db: Session = Depends(get_db)):
    new_violation = Violation(**violation.dict())
    db.add(new_violation)
    db.commit()
    db.refresh(new_violation)
    return new_violation

# Get a specific violation by ID
@router.get("/violations/{violation_id}", response_model=ViolationResponse)
def get_violation(violation_id: int, db: Session = Depends(get_db)):
    violation = db.query(Violation).filter(Violation.id == violation_id).first()
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    return violation

# Get all violations for a specific Address
@router.get("/violations/address/{address_id}", response_model=List[ViolationResponse])
def get_violations_by_address(address_id: int, db: Session = Depends(get_db)):
    violations = db.query(Violation).filter(Violation.address_id == address_id).all()
    return violations
