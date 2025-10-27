from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List
from models import Code, Violation, ViolationCode
from schemas import CodeCreate, CodeResponse, CodeViolationSummary
from database import get_db

router = APIRouter()

# Get all codes
@router.get("/codes/", response_model=List[CodeResponse])
def get_codes(db: Session = Depends(get_db)):
    counts = dict(
        db.query(ViolationCode.code_id, func.count(ViolationCode.id))
        .group_by(ViolationCode.code_id)
        .all()
    )
    # Prefer created_at if available, else fallback to id
    try:
        codes = db.query(Code).order_by(Code.created_at.desc()).all()
    except Exception:
        codes = db.query(Code).order_by(Code.id.desc()).all()

    response_payload: List[CodeResponse] = []
    for code in codes:
        response_payload.append(
            CodeResponse.model_validate({
                "id": code.id,
                "chapter": code.chapter,
                "section": code.section,
                "name": code.name,
                "description": code.description,
                "created_at": code.created_at,
                "updated_at": code.updated_at,
                "violation_count": counts.get(code.id, 0),
            })
        )
    return response_payload

# Create a new code
@router.post("/codes/", response_model=CodeResponse)
def create_code(code: CodeCreate, db: Session = Depends(get_db)):
    chapter = (code.chapter or '').strip()
    section = (code.section or '').strip()
    if chapter and section:
        conflict = (
            db.query(Code)
            .filter(func.lower(Code.chapter) == chapter.lower(), func.lower(Code.section) == section.lower())
            .first()
        )
        if conflict:
            raise HTTPException(status_code=409, detail='Code with this chapter and section already exists')

    new_code = Code(**code.dict())
    db.add(new_code)
    db.commit()
    db.refresh(new_code)
    return new_code

# Get a specific code by ID
@router.get("/codes/{code_id}", response_model=CodeResponse)
def get_code(code_id: int, db: Session = Depends(get_db)):
    code = db.query(Code).filter(Code.id == code_id).first()
    if not code:
        raise HTTPException(status_code=404, detail="Code not found")

    violations = (
        db.query(Violation)
        .join(ViolationCode, ViolationCode.violation_id == Violation.id)
        .options(joinedload(Violation.address))
        .filter(ViolationCode.code_id == code_id)
        .order_by(Violation.created_at.desc())
        .all()
    )

    violation_summaries: List[CodeViolationSummary] = []
    for violation in violations:
        try:
            deadline_date = violation.deadline_date if violation.deadline else None
        except Exception:
            deadline_date = None

        violation_summaries.append(
            CodeViolationSummary(
                id=violation.id,
                description=violation.description,
                status=violation.status,
                address_id=violation.address_id,
                inspection_id=violation.inspection_id,
                business_id=violation.business_id,
                deadline=violation.deadline,
                deadline_date=deadline_date,
                combadd=violation.address.combadd if violation.address else None,
                violation_type=violation.violation_type,
                created_at=violation.created_at,
                updated_at=violation.updated_at,
            )
        )

    return CodeResponse.model_validate({
        "id": code.id,
        "chapter": code.chapter,
        "section": code.section,
        "name": code.name,
        "description": code.description,
        "created_at": code.created_at,
        "updated_at": code.updated_at,
        "violation_count": len(violation_summaries),
        "violations": [summary.model_dump() for summary in violation_summaries],
    })

# Delete a code by ID
@router.delete("/codes/{code_id}", status_code=204)
def delete_code(code_id: int, db: Session = Depends(get_db)):
    code = db.query(Code).filter(Code.id == code_id).first()
    if not code:
        raise HTTPException(status_code=404, detail="Code not found")
    try:
        db.delete(code)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Unable to delete code due to related records")

# Update a code by ID
@router.patch("/codes/{code_id}", response_model=CodeResponse)
@router.put("/codes/{code_id}", response_model=CodeResponse)
def update_code(code_id: int, payload: CodeCreate, db: Session = Depends(get_db)):
    code = db.query(Code).filter(Code.id == code_id).first()
    if not code:
        raise HTTPException(status_code=404, detail="Code not found")

    # Enforce uniqueness of chapter+section if both provided
    chapter = (payload.chapter or '').strip()
    section = (payload.section or '').strip()
    if chapter and section:
        conflict = (
            db.query(Code)
            .filter(
                func.lower(Code.chapter) == chapter.lower(),
                func.lower(Code.section) == section.lower(),
                Code.id != code_id
            )
            .first()
        )
        if conflict:
            raise HTTPException(status_code=409, detail='Code with this chapter and section already exists')

    # Apply updates
    code.chapter = payload.chapter
    code.section = payload.section
    code.name = payload.name
    code.description = payload.description

    try:
        db.add(code)
        db.commit()
        db.refresh(code)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Unable to update code")

    return code