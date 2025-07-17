
from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.orm import Session, joinedload
from typing import List
from models import Citation, Violation, Code
from schemas import CitationCreate, CitationResponse, ViolationResponse
from database import get_db

router = APIRouter()

# PATCH endpoint to update citation status (and other fields if needed)
@router.patch("/citations/{citation_id}", response_model=CitationResponse)
def update_citation_status(citation_id: int, data: dict = Body(...), db: Session = Depends(get_db)):
    citation = db.query(Citation).filter(Citation.id == citation_id).first()
    if not citation:
        raise HTTPException(status_code=404, detail="Citation not found")
    # Only update fields that are present in the request
    if "status" in data:
        citation.status = data["status"]
    # Add more fields here if you want to allow editing them
    db.commit()
    db.refresh(citation)
    # Optionally add code_name to response if needed
    code = db.query(Code).filter(Code.id == citation.code_id).first()
    citation_dict = citation.__dict__.copy()
    citation_dict['code_name'] = code.name if code else None
    return citation_dict

# Get all citations
@router.get("/citations/", response_model=List[CitationResponse])
def get_citations(skip: int = 0, db: Session = Depends(get_db)):
    citations = (
        db.query(Citation)
        .options(
            joinedload(Citation.violation).joinedload(Violation.address)
        )
        .order_by(Citation.created_at.desc())
        .offset(skip)
        .all()
    )
    
    # Add combadd to the response
    response = []
    for citation in citations:
        citation_dict = citation.__dict__
        citation_dict['combadd'] = citation.violation.address.combadd
        response.append(citation_dict)
    
    return response

# Create a new citation
@router.post("/citations/", response_model=CitationResponse)
def create_citation(citation: CitationCreate, db: Session = Depends(get_db)):
    new_citation = Citation(**citation.dict())
    db.add(new_citation)
    db.commit()
    db.refresh(new_citation)
    # Fetch code name for response
    code = db.query(Code).filter(Code.id == new_citation.code_id).first()
    citation_dict = new_citation.__dict__.copy()
    citation_dict['code_name'] = code.name if code else None
    return citation_dict

# Get a specific citation by ID
@router.get("/citations/{citation_id}", response_model=CitationResponse)
def get_citation(citation_id: int, db: Session = Depends(get_db)):
    citation = db.query(Citation).filter(Citation.id == citation_id).first()
    if not citation:
        raise HTTPException(status_code=404, detail="Citation not found")
    # Fetch code name for response
    code = db.query(Code).filter(Code.id == citation.code_id).first()
    citation_dict = citation.__dict__.copy()
    citation_dict['code_name'] = code.name if code else None
    return citation_dict

@router.get("/citations/address/{address_id}", response_model=List[CitationResponse])
def get_citations_by_address(address_id: int, db: Session = Depends(get_db)):
    # First, find all violations for the given address_id
    violations = db.query(Violation).filter(Violation.address_id == address_id).all()

    # Get the ids of those violations
    violation_ids = [violation.id for violation in violations]

    # Then, find all citations associated with those violations
    citations = db.query(Citation).filter(Citation.violation_id.in_(violation_ids)).all()

    # Manually serialize each citation
    serialized_citations = [
        {
            "id": citation.id,
            "violation_id": citation.violation_id,
            "deadline": citation.deadline.strftime('%Y-%m-%d') if citation.deadline else None,
            "created_at": citation.created_at,
            "updated_at": citation.updated_at,
        }
        for citation in citations
    ]

    return serialized_citations
