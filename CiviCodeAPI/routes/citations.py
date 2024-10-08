from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from models import Citation, Violation
from schemas import CitationCreate, CitationResponse
from database import get_db

router = APIRouter()

# Get all citations
@router.get("/citations/", response_model=List[CitationResponse])
def get_citations(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    citations = db.query(Citation).offset(skip).limit(limit).all()
    return citations

# Create a new citation
@router.post("/citations/", response_model=CitationResponse)
def create_citation(citation: CitationCreate, db: Session = Depends(get_db)):
    new_citation = Citation(**citation.dict())
    db.add(new_citation)
    db.commit()
    db.refresh(new_citation)
    return new_citation

# Get a specific citation by ID
@router.get("/citations/{citation_id}", response_model=CitationResponse)
def get_citation(citation_id: int, db: Session = Depends(get_db)):
    citation = db.query(Citation).filter(Citation.id == citation_id).first()
    if not citation:
        raise HTTPException(status_code=404, detail="Citation not found")
    return citation

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
