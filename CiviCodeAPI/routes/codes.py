from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from models import Code
from schemas import CodeCreate, CodeResponse
from database import get_db

router = APIRouter()

# Get all codes
@router.get("/codes/", response_model=List[CodeResponse])
def get_codes(db: Session = Depends(get_db)):
    # Prefer created_at if available, else fallback to id
    try:
        codes = db.query(Code).order_by(Code.created_at.desc()).all()
    except Exception:
        codes = db.query(Code).order_by(Code.id.desc()).all()
    return codes

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
    return code

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