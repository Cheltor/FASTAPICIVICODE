from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from models import License, Inspection, Address
from schemas import LicenseCreate, LicenseResponse, LicenseUpdate
from database import get_db

router = APIRouter()

# Show all the licenses
@router.get("/licenses/", response_model=List[LicenseResponse])
def get_licenses(inspection_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(License)
    if inspection_id is not None:
        q = q.filter(License.inspection_id == inspection_id)
    licenses = q.all()

    # gather inspection -> address mapping
    insp_ids = [lic.inspection_id for lic in licenses]
    if not insp_ids:
        return licenses
    inspections = (
        db.query(Inspection.id, Inspection.address_id, Address.combadd)
        .join(Address, Address.id == Inspection.address_id)
        .filter(Inspection.id.in_(insp_ids))
        .all()
    )
    insp_map = {row.id: {"address_id": row.address_id, "combadd": row.combadd} for row in inspections}

    augmented = []
    for lic in licenses:
        base = {k: getattr(lic, k) for k in lic.__dict__ if not k.startswith('_')}
        extra = insp_map.get(lic.inspection_id, {})
        base.update(extra)
        augmented.append(base)
    return augmented

@router.get("/licenses/{license_id}", response_model=LicenseResponse)
def get_license(license_id: int, db: Session = Depends(get_db)):
    lic = db.query(License).filter(License.id == license_id).first()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    insp = db.query(Inspection).filter(Inspection.id == lic.inspection_id).first()
    combadd = None
    address_id = None
    if insp:
        addr = db.query(Address).filter(Address.id == insp.address_id).first()
        if addr:
            combadd = addr.combadd
            address_id = addr.id
    data = {k: getattr(lic, k) for k in lic.__dict__ if not k.startswith('_')}
    data['combadd'] = combadd
    data['address_id'] = address_id
    return data

@router.post("/licenses/", response_model=LicenseResponse)
def create_license(license_in: LicenseCreate, db: Session = Depends(get_db)):
    # avoid duplicate for same inspection
    existing = db.query(License).filter(License.inspection_id == license_in.inspection_id).first()
    if existing:
        return existing

    data = license_in.dict()

    # If business_id isn't provided, inherit from the related inspection (if any)
    if not data.get("business_id"):
        insp = db.query(Inspection).filter(Inspection.id == data.get("inspection_id")).first()
        if insp and insp.business_id:
            data["business_id"] = insp.business_id

    # Determine fiscal year (July 1 - June 30). Fiscal year labeled by ending year.
    today = date.today()
    # If we're before July, still in prior fiscal year window that ends current calendar year
    if today.month < 7:  # Jan-Jun
        fy_end_year = today.year
    else:  # Jul-Dec
        fy_end_year = today.year + 1
    fiscal_year = f"{fy_end_year - 1}-{fy_end_year}"

    # date_issued default to today if not provided
    if not data.get("date_issued"):
        data["date_issued"] = today

    # expiration is June 30 of fiscal year end
    if not data.get("expiration_date"):
        data["expiration_date"] = date(fy_end_year, 6, 30)

    data["fiscal_year"] = fiscal_year

    lic = License(**data)
    db.add(lic)
    db.commit()
    db.refresh(lic)

    # augment with address info for consistency
    insp = db.query(Inspection).filter(Inspection.id == lic.inspection_id).first()
    combadd = None
    address_id = None
    if insp:
        addr = db.query(Address).filter(Address.id == insp.address_id).first()
        if addr:
            combadd = addr.combadd
            address_id = addr.id
    data_out = {k: getattr(lic, k) for k in lic.__dict__ if not k.startswith('_')}
    data_out['combadd'] = combadd
    data_out['address_id'] = address_id
    return data_out

@router.put("/licenses/{license_id}", response_model=LicenseResponse)
def update_license(license_id: int, license_in: LicenseUpdate, db: Session = Depends(get_db)):
    lic = db.query(License).filter(License.id == license_id).first()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")

    update_fields = license_in.dict(exclude_unset=True)
    for key, value in update_fields.items():
        setattr(lic, key, value)

    db.add(lic)
    db.commit()
    db.refresh(lic)

    # augment with address info for consistency
    insp = db.query(Inspection).filter(Inspection.id == lic.inspection_id).first()
    combadd = None
    address_id = None
    if insp:
        addr = db.query(Address).filter(Address.id == insp.address_id).first()
        if addr:
            combadd = addr.combadd
            address_id = addr.id
    data_out = {k: getattr(lic, k) for k in lic.__dict__ if not k.startswith('_')}
    data_out['combadd'] = combadd
    data_out['address_id'] = address_id
    return data_out