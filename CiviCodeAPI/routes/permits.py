from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from database import get_db
from models import Permit, Inspection, Address, Business
from schemas import PermitCreate, PermitResponse

router = APIRouter()

@router.get("/permits/", response_model=List[PermitResponse])
def get_permits(inspection_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Permit)
    if inspection_id is not None:
        q = q.filter(Permit.inspection_id == inspection_id)
    permits = q.all()

    insp_ids = [p.inspection_id for p in permits]
    if not insp_ids:
        return permits
    inspections = (
        db.query(Inspection.id, Inspection.address_id, Address.combadd)
        .join(Address, Address.id == Inspection.address_id)
        .filter(Inspection.id.in_(insp_ids))
        .all()
    )
    insp_map = {row.id: {"address_id": row.address_id, "combadd": row.combadd} for row in inspections}

    augmented = []
    for p in permits:
        base = {k: getattr(p, k) for k in p.__dict__ if not k.startswith('_')}
        extra = insp_map.get(p.inspection_id, {})
        base.update(extra)
        augmented.append(base)
    return augmented

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

@router.get("/permits/{permit_id}", response_model=PermitResponse)
def get_permit(permit_id: int, db: Session = Depends(get_db)):
    permit = db.query(Permit).filter(Permit.id == permit_id).first()
    if not permit:
        raise HTTPException(status_code=404, detail="Permit not found")
    insp = db.query(Inspection).filter(Inspection.id == permit.inspection_id).first()
    combadd = None
    address_id = None
    if insp:
        addr = db.query(Address).filter(Address.id == insp.address_id).first()
        if addr:
            combadd = addr.combadd
            address_id = addr.id
    data = {k: getattr(permit, k) for k in permit.__dict__ if not k.startswith('_')}
    data['combadd'] = combadd
    data['address_id'] = address_id
    return data
