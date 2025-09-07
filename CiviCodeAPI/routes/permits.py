from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from models import Permit
from schemas import PermitCreate, PermitResponse

router = APIRouter()

@router.get("/permits/", response_model=List[PermitResponse])
def get_permits(inspection_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Permit)
    if inspection_id is not None:
        q = q.filter(Permit.inspection_id == inspection_id)
    return q.all()

@router.post("/permits/", response_model=PermitResponse)
def create_permit(permit_in: PermitCreate, db: Session = Depends(get_db)):
    # avoid duplicate for same inspection
    existing = db.query(Permit).filter(Permit.inspection_id == permit_in.inspection_id).first()
    if existing:
        return existing
    permit = Permit(**permit_in.dict())
    db.add(permit)
    db.commit()
    db.refresh(permit)
    return permit
