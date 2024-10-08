from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from models import User
from schemas import UserResponse
from database import get_db

router = APIRouter()

# Show all the users
@router.get("/users/", response_model=List[UserResponse])
def get_users(skip: int = 0, db: Session = Depends(get_db)):
    users = db.query(User).offset(skip).all()
    return users