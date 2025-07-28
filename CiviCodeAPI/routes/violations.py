from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session, joinedload
from typing import List
from models import Violation, Citation
import schemas
from database import get_db
from sqlalchemy import desc
import models

router = APIRouter()

# Get all violations
@router.get("/violations/", response_model=List[schemas.ViolationResponse])
def get_violations(skip: int = 0, db: Session = Depends(get_db)):
    violations = (
        db.query(Violation)
        .options(
            joinedload(Violation.address),
            joinedload(Violation.codes),
            joinedload(Violation.user)  # Eagerly load User relationship
        )
        .order_by(desc(Violation.created_at))
        .offset(skip)
        .all()
    )

    response = []
    for violation in violations:
        violation_dict = violation.__dict__.copy()
        violation_dict['combadd'] = violation.address.combadd if violation.address else None
        violation_dict['deadline_date'] = violation.deadline_date
        violation_dict['codes'] = violation.codes
        violation_dict['user'] = schemas.UserResponse.from_orm(violation.user) if getattr(violation, 'user', None) else None
        response.append(violation_dict)
    return response

# Create a new violation
@router.post("/violations/", response_model=schemas.ViolationResponse)
def create_violation(violation: schemas.ViolationCreate, db: Session = Depends(get_db)):
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
@router.get("/violation/{violation_id}", response_model=schemas.ViolationResponse)
def get_violation(violation_id: int, db: Session = Depends(get_db)):
    violation = (
        db.query(Violation)
        .filter(Violation.id == violation_id)
        .options(
            joinedload(Violation.address),
            joinedload(Violation.codes),
            joinedload(Violation.user)  # Eagerly load the user relationship
        )
        .first()
    )
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    # Add combadd and codes to the response
    violation_dict = violation.__dict__.copy()
    violation_dict['combadd'] = violation.address.combadd if violation.address else None
    violation_dict['deadline_date'] = violation.deadline_date
    violation_dict['codes'] = violation.codes
    violation_dict['user'] = schemas.UserResponse.from_orm(violation.user) if getattr(violation, 'user', None) else None
    violation_dict['violation_comments'] = [
        {
            'id': vc.id,
            'content': vc.content,
            'user_id': vc.user_id,
            'violation_id': vc.violation_id,
            'created_at': vc.created_at,
            'updated_at': vc.updated_at,
            'user': schemas.UserResponse.from_orm(vc.user) if getattr(vc, 'user', None) else None
        }
        for vc in violation.violation_comments
    ] if hasattr(violation, 'violation_comments') else []
    return violation_dict

    print("violation.user:", violation.user)
    print("violation_dict['user']:", violation_dict.get('user'))


# Get all violations for a specific Address
@router.get("/violations/address/{address_id}", response_model=List[schemas.ViolationResponse])
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
@router.get("/violation/{violation_id}/citations", response_model=List[schemas.CitationResponse])
def get_citations_by_violation(violation_id: int, db: Session = Depends(get_db)):
    citations = (
        db.query(Citation)
        .options(
            joinedload(Citation.violation).joinedload(Violation.address),
            joinedload(Citation.code),
            joinedload(Citation.user)  # Eagerly load the User relationship
        )
        .filter(Citation.violation_id == violation_id)
        .all()
    )

    # Add combadd, code_name, and user to the response
    response = []
    for citation in citations:
        citation_dict = citation.__dict__.copy()
        citation_dict['combadd'] = citation.violation.address.combadd if citation.violation and citation.violation.address else None
        citation_dict['code_name'] = citation.code.name if citation.code else None
        citation_dict['user'] = schemas.UserResponse.from_orm(citation.user) if getattr(citation, 'user', None) else None
        response.append(citation_dict)
    return response

# Add a comment to a violation
@router.post("/violation/{violation_id}/comments", response_model=schemas.ViolationCommentResponse)
def add_violation_comment(violation_id: int, comment: schemas.ViolationCommentCreate, db: Session = Depends(get_db)):
    # Ensure violation exists
    violation = db.query(models.Violation).filter(models.Violation.id == violation_id).first()
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    # Create new comment
    new_comment = models.ViolationComment(
        content=comment.content,
        user_id=comment.user_id,
        violation_id=violation_id
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    # Optionally, fetch user info for response
    user = db.query(models.User).filter(models.User.id == new_comment.user_id).first()
    user_response = schemas.UserResponse.from_orm(user) if user else None
    return schemas.ViolationCommentResponse(
        id=new_comment.id,
        content=new_comment.content,
        user_id=new_comment.user_id,
        violation_id=new_comment.violation_id,
        created_at=new_comment.created_at,
        updated_at=new_comment.updated_at,
        user=user_response
    )

# Abate (close) a violation
@router.post("/violation/{violation_id}/abate", response_model=schemas.ViolationResponse)
def abate_violation(violation_id: int, db: Session = Depends(get_db)):
    violation = db.query(models.Violation).options(joinedload(models.Violation.user)).filter(models.Violation.id == violation_id).first()
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    violation.status = 1  # 1 = Resolved/Closed
    db.commit()
    db.refresh(violation)
    violation_dict = violation.__dict__.copy()
    violation_dict['combadd'] = violation.address.combadd if violation.address else None
    violation_dict['deadline_date'] = violation.deadline_date
    violation_dict['codes'] = violation.codes
    violation_dict['user'] = schemas.UserResponse.from_orm(violation.user) if getattr(violation, 'user', None) else None
    violation_dict['violation_comments'] = [
        {
            'id': vc.id,
            'content': vc.content,
            'user_id': vc.user_id,
            'violation_id': vc.violation_id,
            'created_at': vc.created_at,
            'updated_at': vc.updated_at,
            'user': schemas.UserResponse.from_orm(vc.user) if getattr(vc, 'user', None) else None
        }
        for vc in violation.violation_comments
    ] if hasattr(violation, 'violation_comments') else []
    return violation_dict

# Reopen a violation (set status back to current)
@router.post("/violation/{violation_id}/reopen", response_model=schemas.ViolationResponse)
def reopen_violation(violation_id: int, db: Session = Depends(get_db)):
    violation = db.query(models.Violation).options(joinedload(models.Violation.user)).filter(models.Violation.id == violation_id).first()
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    violation.status = 0  # 0 = Current/Open
    db.commit()
    db.refresh(violation)
    violation_dict = violation.__dict__.copy()
    violation_dict['combadd'] = violation.address.combadd if violation.address else None
    violation_dict['deadline_date'] = violation.deadline_date
    violation_dict['codes'] = violation.codes
    violation_dict['user'] = schemas.UserResponse.from_orm(violation.user) if getattr(violation, 'user', None) else None
    violation_dict['violation_comments'] = [
        {
            'id': vc.id,
            'content': vc.content,
            'user_id': vc.user_id,
            'violation_id': vc.violation_id,
            'created_at': vc.created_at,
            'updated_at': vc.updated_at,
            'user': schemas.UserResponse.from_orm(vc.user) if getattr(vc, 'user', None) else None
        }
        for vc in violation.violation_comments
    ] if hasattr(violation, 'violation_comments') else []
    return violation_dict

