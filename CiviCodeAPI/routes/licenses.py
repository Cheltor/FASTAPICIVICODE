from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from models import License
from schemas import LicenseCreate, LicenseResponse
from database import get_db

router = APIRouter()

# Show all the licenses
@router.get("/licenses/", response_model=List[LicenseResponse])
def get_licenses(db: Session = Depends(get_db)):
    licenses = db.query(License).all()
    return licenses