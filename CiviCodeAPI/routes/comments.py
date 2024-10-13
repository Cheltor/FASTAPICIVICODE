from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from models import Comment, ContactComment, ActiveStorageAttachment, ActiveStorageBlob, User
from schemas import CommentCreate, CommentResponse, ContactCommentCreate, ContactCommentResponse, UserResponse
from database import get_db

router = APIRouter()

# Get all comments
@router.get("/comments/", response_model=List[CommentResponse])
def get_comments(skip: int = 0, db: Session = Depends(get_db)):
    comments = db.query(Comment).offset(skip).all()
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
    comment_responses = []
    for comment in comments:
        user = db.query(User).filter(User.id == comment.user_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        comment_responses.append(CommentResponse(
            id=comment.id,
            content=comment.content,
            user_id=comment.user_id,  # Make sure to include the user_id here
            user=UserResponse(
                id=user.id,
                name=user.name,
                email=user.email,
                phone=user.phone,
                role=user.role,
                created_at=user.created_at,
                updated_at=user.updated_at
            ),
            unit_id=comment.unit_id,
            created_at=comment.created_at,
            updated_at=comment.updated_at
        ))
    return comment_responses




# Get all comments for a specific Contact
@router.get("/comments/contact/{contact_id}", response_model=List[ContactCommentResponse])
def get_comments_by_contact(contact_id: int, db: Session = Depends(get_db)):
    if contact_id is None:
        raise HTTPException(status_code=422, detail="Invalid contact_id")
    comments = db.query(ContactComment).filter(ContactComment.contact_id == contact_id).order_by(ContactComment.created_at.desc()).all()
    return comments

# Fetch Comment photo by ID
@router.get("/comments/address/{address_id}", response_model=List[CommentResponse])
def get_comments_for_address(address_id: int, db: Session = Depends(get_db)):
    comments = (
        db.query(Comment)
        .filter(Comment.address_id == address_id)
        .all()
    )
    
    # For each comment, fetch associated photos from ActiveStorage
    for comment in comments:
        # Fetch attachments for this comment
        attachments = (
            db.query(ActiveStorageAttachment, ActiveStorageBlob)
            .join(ActiveStorageBlob, ActiveStorageAttachment.blob_id == ActiveStorageBlob.id)
            .filter(
                ActiveStorageAttachment.record_type == 'Comment',
                ActiveStorageAttachment.record_id == comment.id,
                ActiveStorageAttachment.name == 'photos'  # 'photos' is the name of the attachment
            )
            .all()
        )
        
        # Store photo URLs in a list associated with the comment
        comment.photos = [
            f"https://codeenforcement.blob.core.windows.net/ce-container/{attachment[1].key}"
            for attachment in attachments
        ]
    
    return comments