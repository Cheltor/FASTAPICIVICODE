from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from database import get_db
from models import Permit, Inspection, Address, Business
from schemas import PermitCreate, PermitResponse, PermitUpdate

router = APIRouter()

@router.get("/permits/", response_model=List[PermitResponse])
def get_permits(inspection_id: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Get all permits, optionally filtered by inspection ID.

    Args:
        inspection_id (int, optional): Filter by inspection ID.
        db (Session): The database session.

    Returns:
        list[PermitResponse]: A list of permits.
    """
    q = db.query(Permit)
    if inspection_id is not None:
        q = q.filter(Permit.inspection_id == inspection_id)
    permits = q.order_by(Permit.created_at.desc()).all()

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
    """
    Create a new permit.

    Args:
        permit_in (PermitCreate): Permit data.
        db (Session): The database session.

    Returns:
        PermitResponse: The created permit.
    """
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
    """
    Get a permit by ID.

    Args:
        permit_id (int): The ID of the permit.
        db (Session): The database session.

    Returns:
        PermitResponse: The permit details.

    Raises:
        HTTPException: If permit is not found.
    """
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


# Return permits for a given address (via inspections at that address).
# Important: if there are no permits for the address, return an empty list (200), not a 404.
@router.get("/permits/address/{address_id}", response_model=List[PermitResponse])
def get_permits_by_address(address_id: int, db: Session = Depends(get_db)):
    """
    Get permits for an address (via linked inspections).

    Args:
        address_id (int): The ID of the address.
        db (Session): The database session.

    Returns:
        list[PermitResponse]: A list of permits.
    """
    # Find all inspection ids for this address
    insp_rows = db.query(Inspection.id).filter(Inspection.address_id == address_id).all()
    insp_ids = [r.id for r in insp_rows]

    # If there are no inspections (or none), return empty list rather than 404
    if not insp_ids:
        return []

    # Query permits whose inspection_id is one of the inspections for this address
    permits = (
        db.query(Permit)
        .filter(Permit.inspection_id.in_(insp_ids))
        .order_by(Permit.created_at.desc())
        .all()
    )

    if not permits:
        return []

    # Fetch inspection -> address context (combadd)
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


@router.put("/permits/{permit_id}", response_model=PermitResponse)
def update_permit(permit_id: int, permit_in: PermitUpdate, db: Session = Depends(get_db)):
    """
    Update a permit.

    Args:
        permit_id (int): The ID of the permit.
        permit_in (PermitUpdate): Updated data.
        db (Session): The database session.

    Returns:
        PermitResponse: The updated permit.

    Raises:
        HTTPException: If permit is not found or update fails.
    """
    permit = db.query(Permit).filter(Permit.id == permit_id).first()
    if not permit:
        raise HTTPException(status_code=404, detail="Permit not found")

    # Update only provided fields
    for field in ("permit_type", "business_id", "permit_number", "date_issued", "expiration_date", "conditions", "paid"):
        val = getattr(permit_in, field)
        # Normalize empty strings to None so frontend can send empty values from inputs
        if isinstance(val, str) and val.strip() == "":
            val = None
        if val is not None:
            setattr(permit, field, val)

    try:
        db.add(permit)
        db.commit()
        db.refresh(permit)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Failed to update permit")

    # Attach address context like in get_permit
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

# Delete a permit by ID
@router.delete("/permits/{permit_id}", status_code=204)
def delete_permit(permit_id: int, db: Session = Depends(get_db)):
    """
    Delete a permit.

    Args:
        permit_id (int): The ID of the permit.
        db (Session): The database session.

    Raises:
        HTTPException: If permit not found or deletion fails.
    """
    permit = db.query(Permit).filter(Permit.id == permit_id).first()
    if not permit:
        raise HTTPException(status_code=404, detail="Permit not found")
    try:
        db.delete(permit)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Unable to delete permit due to related records")
