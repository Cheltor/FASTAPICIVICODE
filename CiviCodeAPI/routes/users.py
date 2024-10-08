from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from models import User
from schemas import UserResponse
from database import get_db

router = APIRouter()

@router.get("/users/", response_model=List[UserResponse])
def get_users(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    users = db.query(User).offset(skip).limit(limit).all()
    return users