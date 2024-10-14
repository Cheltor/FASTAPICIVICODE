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
@router.get("/comments/{comment_id}/photos")
def get_comment_photos(comment_id: int, db: Session = Depends(get_db)):
    # Retrieve the attachments for the comment
    attachments = db.query(ActiveStorageAttachment).filter_by(record_id=comment_id, record_type='Comment', name='photos').all()
    
    if not attachments:
        raise HTTPException(status_code=404, detail="Photos not found for this comment")

    photos = []
    
    for attachment in attachments:
        # Retrieve the associated blob for each attachment
        blob = db.query(ActiveStorageBlob).filter_by(id=attachment.blob_id).first()
        
        if not blob:
            continue  # Skip if no blob found (edge case)
        
        # Construct the Azure storage URL for each photo
        photo_url = f"https://codeenforcement.blob.core.windows.net/ce-container/{blob.key}"
        
        # Append the photo details to the list
        photos.append({
            "filename": blob.filename,
            "content_type": blob.content_type,
            "url": photo_url,
        })
    
    return photos

# Create a new comment for a Contact
@router.post("/comments/{contact_id}/contact/", response_model=ContactCommentResponse)
def create_contact_comment(contact_id: int, comment: ContactCommentCreate, db: Session = Depends(get_db)):
    new_comment = ContactComment(**comment.dict())
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment