from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from models import Comment
from schemas import CommentCreate, CommentResponse
from database import get_db

router = APIRouter()

# Get all comments
@router.get("/comments/", response_model=List[CommentResponse])
def get_comments(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    comments = db.query(Comment).offset(skip).limit(limit).all()
    return comments

# Create a new comment
@router.post("/comments/", response_model=CommentResponse)
def create_comment(comment: CommentCreate, db: Session = Depends(get_db)):
    new_comment = Comment(**comment.dict())
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment

# Get all comments for a specific Address
@router.get("/comments/address/{address_id}", response_model=List[CommentResponse])
def get_comments_by_address(address_id: int, db: Session = Depends(get_db)):
  comments = db.query(Comment).filter(Comment.address_id == address_id).order_by(Comment.created_at.desc()).all()
  return comments