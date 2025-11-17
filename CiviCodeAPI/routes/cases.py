from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from .. import schemas, models
from ..database import get_db

router = APIRouter()

@router.post("/cases/", response_model=schemas.CaseResponse)
def create_case(case: schemas.CaseCreate, db: Session = Depends(get_db)):
    db_case = models.Case(**case.dict())
    db.add(db_case)
    db.commit()
    db.refresh(db_case)
    return db_case

@router.get("/cases/", response_model=List[schemas.CaseResponse])
def read_cases(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    cases = db.query(models.Case).offset(skip).limit(limit).all()
    return cases

@router.get("/cases/{case_id}", response_model=schemas.CaseResponse)
def read_case(case_id: int, db: Session = Depends(get_db)):
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return db_case

@router.put("/cases/{case_id}", response_model=schemas.CaseResponse)
def update_case(case_id: int, case: schemas.CaseCreate, db: Session = Depends(get_db)):
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    for var, value in vars(case).items():
        setattr(db_case, var, value) if value else None
    db.commit()
    db.refresh(db_case)
    return db_case

@router.delete("/cases/{case_id}", response_model=schemas.CaseResponse)
def delete_case(case_id: int, db: Session = Depends(get_db)):
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    db.delete(db_case)
    db.commit()
    return db_case

@router.post("/cases/{case_id}/comments/", response_model=schemas.CaseCommentResponse)
def create_case_comment(case_id: int, comment: schemas.CaseCommentCreate, db: Session = Depends(get_db)):
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    db_comment = models.CaseComment(**comment.dict(), case_id=case_id)
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment
