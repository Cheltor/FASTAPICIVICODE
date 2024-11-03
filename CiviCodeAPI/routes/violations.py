from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session, joinedload
from typing import List
from models import Violation, Citation
from schemas import ViolationCreate, ViolationResponse, CitationResponse
from database import get_db
from sqlalchemy import desc

router = APIRouter()

# Get all violations
@router.get("/violations/", response_model=List[ViolationResponse])
def get_violations(skip: int = 0, db: Session = Depends(get_db)):
    violations = (
        db.query(Violation)
        .options(joinedload(Violation.address))  # Eagerly load the Address relationship
        .order_by(desc(Violation.created_at))
        .offset(skip)
        .all()
    )

    
    
    # Add combadd to the response
    response = []
    for violation in violations:
        violation_dict = violation.__dict__
        violation_dict['combadd'] = violation.address.combadd if violation.address else None
        violation_dict['deadline_date'] = violation.deadline_date  # Directly access the computed property
        response.append(violation_dict)
    
    return response

# Create a new violation
@router.post("/violations/", response_model=ViolationResponse)
def create_violation(violation: ViolationCreate, db: Session = Depends(get_db)):
    new_violation = Violation(**violation.dict())
    db.add(new_violation)
    db.commit()
    db.refresh(new_violation)
    return new_violation

# Get a specific violation by ID
@router.get("/violation/{violation_id}", response_model=ViolationResponse)
def get_violation(violation_id: int, db: Session = Depends(get_db)):
    violation = (
        db.query(Violation)
        .filter(Violation.id == violation_id)
        .options(joinedload(Violation.address))  # Eagerly load the Address relationship
        .first()
    )
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    
    # Add combadd to the response
    violation_dict = violation.__dict__
    violation_dict['combadd'] = violation.address.combadd if violation.address else None
    violation_dict['deadline_date'] = violation.deadline_date  # Access computed property
    
    return violation_dict


# Get all violations for a specific Address
@router.get("/violations/address/{address_id}", response_model=List[ViolationResponse])
def get_violations_by_address(address_id: int, db: Session = Depends(get_db)):
    violations = db.query(Violation).filter(Violation.address_id == address_id).all()
    return violations

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