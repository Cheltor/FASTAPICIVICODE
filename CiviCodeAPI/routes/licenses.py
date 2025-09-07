from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from models import License
from schemas import LicenseCreate, LicenseResponse
from database import get_db

router = APIRouter()

# Show all the licenses
@router.get("/licenses/", response_model=List[LicenseResponse])
def get_licenses(inspection_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(License)
    if inspection_id is not None:
        q = q.filter(License.inspection_id == inspection_id)
    licenses = q.all()
    return licenses

@router.get("/licenses/{license_id}", response_model=LicenseResponse)
def get_license(license_id: int, db: Session = Depends(get_db)):
    lic = db.query(License).filter(License.id == license_id).first()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    return lic

@router.post("/licenses/", response_model=LicenseResponse)
def create_license(license_in: LicenseCreate, db: Session = Depends(get_db)):
    # avoid duplicate for same inspection
    existing = db.query(License).filter(License.inspection_id == license_in.inspection_id).first()
    if existing:
        return existing
    lic = License(**license_in.dict())
    db.add(lic)
    db.commit()
    db.refresh(lic)
    return lic