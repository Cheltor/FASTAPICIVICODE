from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session, joinedload
from typing import List
from models import Violation, Citation
from schemas import ViolationCreate, ViolationResponse, CitationResponse
from database import get_db
from sqlalchemy import desc
import models

router = APIRouter()

# Get all violations
@router.get("/violations/", response_model=List[ViolationResponse])
def get_violations(skip: int = 0, db: Session = Depends(get_db)):
    violations = (
        db.query(Violation)
        .options(joinedload(Violation.address), joinedload(Violation.codes))  # Eagerly load Address and Codes
        .order_by(desc(Violation.created_at))
        .offset(skip)
        .all()
    )

    # Add combadd and codes to the response
    response = []
    for violation in violations:
        violation_dict = violation.__dict__.copy()
        violation_dict['combadd'] = violation.address.combadd if violation.address else None
        violation_dict['deadline_date'] = violation.deadline_date  # Directly access the computed property
        violation_dict['codes'] = violation.codes
        response.append(violation_dict)
    return response

# Create a new violation
@router.post("/violations/", response_model=ViolationResponse)
def create_violation(violation: ViolationCreate, db: Session = Depends(get_db)):
    violation_data = violation.dict(exclude={"codes"})
    # Ensure violation_type is set, default to "doorhanger" if not provided
    if not violation_data.get("violation_type"):
        violation_data["violation_type"] = "doorhanger"
    # Always set status to 0 (current) if not provided
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

# Get a specific violation by ID
@router.get("/violation/{violation_id}", response_model=ViolationResponse)
def get_violation(violation_id: int, db: Session = Depends(get_db)):
    violation = (
        db.query(Violation)
        .filter(Violation.id == violation_id)
        .options(joinedload(Violation.address), joinedload(Violation.codes))  # Eagerly load Address and Codes
        .first()
    )
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    # Add combadd and codes to the response
    violation_dict = violation.__dict__.copy()
    violation_dict['combadd'] = violation.address.combadd if violation.address else None
    violation_dict['deadline_date'] = violation.deadline_date  # Access computed property
    violation_dict['codes'] = violation.codes
    return violation_dict


# Get all violations for a specific Address
@router.get("/violations/address/{address_id}", response_model=List[ViolationResponse])
def get_violations_by_address(address_id: int, db: Session = Depends(get_db)):
    violations = db.query(Violation).options(joinedload(Violation.codes)).filter(Violation.address_id == address_id).all()
    # Add codes and deadline_date to the response
    response = []
    for violation in violations:
        violation_dict = violation.__dict__.copy()
        violation_dict['codes'] = violation.codes
        violation_dict['deadline_date'] = violation.deadline_date  # Ensure this computed property is included
        response.append(violation_dict)
    return response

# Show all citations for a specific Violation
@router.get("/violation/{violation_id}/citations", response_model=List[CitationResponse])
def get_citations_by_violation(violation_id: int, db: Session = Depends(get_db)):
    citations = (
        db.query(Citation)
        .options(
            joinedload(Citation.violation).joinedload(Violation.address),
            joinedload(Citation.code)  # Eagerly load the Code relationship
        )
        .filter(Citation.violation_id == violation_id)
        .all()
    )
    
    # Add combadd and code.name to the response
    response = []
    for citation in citations:
        citation_dict = citation.__dict__
        citation_dict['combadd'] = citation.violation.address.combadd
        citation_dict['code_name'] = citation.code.name if citation.code else None
        response.append(citation_dict)
    
    return response