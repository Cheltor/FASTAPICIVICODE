from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date
from CiviCodeAPI.models import License, Inspection, Address, Business
from CiviCodeAPI.schemas import LicenseCreate, LicenseResponse, LicenseUpdate
from CiviCodeAPI.database import get_db

router = APIRouter()

# Show all the licenses
@router.get("/licenses/", response_model=List[LicenseResponse])
def get_licenses(inspection_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(License)
    if inspection_id is not None:
        q = q.filter(License.inspection_id == inspection_id)
    licenses = q.order_by(License.created_at.desc()).all()

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

    # Enforce license number uniqueness when provided
    license_number = (license_in.license_number or '').strip() if hasattr(license_in, 'license_number') else ''
    if license_number:
        conflict = (
            db.query(License)
            .filter(func.lower(License.license_number) == license_number.lower())
            .first()
        )
        if conflict:
            raise HTTPException(status_code=409, detail='License number already exists')

    data = license_in.dict(exclude={'address_id'})
    if 'license_number' in data:
        data['license_number'] = license_number or None
    address_hint = getattr(license_in, 'address_id', None)

    license_type = data.get('license_type')
    if license_type is None:
        raise HTTPException(status_code=422, detail='license_type is required')

    inspection_id = data.get('inspection_id')
    created_inspection = None

    if not inspection_id:
        if license_type == 1:
            business_id = data.get('business_id')
            if not business_id:
                raise HTTPException(status_code=422, detail='business_id is required for business licenses')
            business = db.query(Business).filter(Business.id == business_id).first()
            if not business:
                raise HTTPException(status_code=404, detail='Business not found')
            if not business.address_id:
                raise HTTPException(status_code=400, detail='Selected business has no address on file')

            created_inspection = Inspection(
                address_id=business.address_id,
                source='Business License',
                business_id=business.id,
            )
        elif license_type in (2, 3):
            if not address_hint:
                raise HTTPException(status_code=422, detail='address_id is required for housing licenses')
            address = db.query(Address).filter(Address.id == address_hint).first()
            if not address:
                raise HTTPException(status_code=404, detail='Address not found')
            created_inspection = Inspection(
                address_id=address.id,
                source='Single Family License' if license_type == 2 else 'Multifamily License',
            )
        else:
            raise HTTPException(status_code=422, detail='Unsupported license type')

        db.add(created_inspection)
        db.commit()
        db.refresh(created_inspection)
        data['inspection_id'] = created_inspection.id
        inspection_id = created_inspection.id

        if license_type == 1:
            data['business_id'] = data.get('business_id') or created_inspection.business_id

    if not data.get('business_id') and inspection_id:
        insp_obj = db.query(Inspection).filter(Inspection.id == inspection_id).first()
        if insp_obj and insp_obj.business_id:
            data['business_id'] = insp_obj.business_id

    today = date.today()
    fy_end_year = today.year if today.month < 7 else today.year + 1
    fiscal_year = f"{fy_end_year - 1}-{fy_end_year}"

    if not data.get('date_issued'):
        data['date_issued'] = today

    if not data.get('expiration_date'):
        data['expiration_date'] = date(fy_end_year, 6, 30)

    data['fiscal_year'] = fiscal_year

    lic = License(**data)
    db.add(lic)
    db.commit()
    db.refresh(lic)

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
    if 'license_number' in update_fields:
        new_number_raw = update_fields['license_number']
        new_number = new_number_raw.strip() if isinstance(new_number_raw, str) else (new_number_raw or None)
        if new_number:
            conflict = (
                db.query(License)
                .filter(func.lower(License.license_number) == new_number.lower(), License.id != license_id)
                .first()
            )
            if conflict:
                raise HTTPException(status_code=409, detail='License number already exists')
            update_fields['license_number'] = new_number
        else:
            update_fields['license_number'] = None
    for key, value in update_fields.items():
        setattr(lic, key, value if value != '' else None)

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

# Delete a license by ID
@router.delete("/licenses/{license_id}", status_code=204)
def delete_license(license_id: int, db: Session = Depends(get_db)):
    lic = db.query(License).filter(License.id == license_id).first()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    try:
        db.delete(lic)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Unable to delete license due to related records")