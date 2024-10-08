from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from models import Code
from schemas import CodeCreate, CodeResponse
from database import get_db

router = APIRouter()

# Get all codes
@router.get("/codes/", response_model=List[CodeResponse])
def get_codes(db: Session = Depends(get_db)):
    codes = db.query(Code).all()
    return codes

# Create a new code
@router.post("/codes/", response_model=CodeResponse)
def create_code(code: CodeCreate, db: Session = Depends(get_db)):
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