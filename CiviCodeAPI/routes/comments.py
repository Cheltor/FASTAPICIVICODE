from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from sqlalchemy.orm import Session
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta
from typing import List, Optional
from models import Comment, ContactComment, ActiveStorageAttachment, ActiveStorageBlob, User, Unit
from schemas import CommentCreate, CommentResponse, ContactCommentCreate, ContactCommentResponse, UserResponse, UnitResponse
from database import get_db
from storage import blob_service_client, container_client, account_name, account_key, CONTAINER_NAME
import os
import logging

router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Get all comments
@router.get("/comments/", response_model=List[CommentResponse])
def get_comments(skip: int = 0, db: Session = Depends(get_db)):
    comments = db.query(Comment).offset(skip).all()
    return comments

# Create a new comment
@router.post("/comments/", response_model=CommentResponse)
def create_comment(comment: CommentCreate, db: Session = Depends(get_db)):
    logger.debug(f"Received payload: {comment.dict()}")
    logger.debug(f"Creating comment with content: {comment.content}, user_id: {comment.user_id}, unit_id: {comment.unit_id}")
    new_comment = Comment(**comment.dict())
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    logger.debug(f"Created comment with ID: {new_comment.id}, unit_id: {new_comment.unit_id}")
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
        unit = None
        if comment.unit_id:
            unit = db.query(Unit).filter(Unit.id == comment.unit_id).first()
        comment_responses.append(CommentResponse(
            id=comment.id,
            content=comment.content,
            user_id=comment.user_id,
            address_id=comment.address_id,  # <-- Ensure address_id is included
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
            unit=UnitResponse(
                id=unit.id,
                number=unit.number,
                address_id=unit.address_id,
                created_at=unit.created_at,
                updated_at=unit.updated_at
            ) if unit else None,
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
    # Check if the comment exists
    comment = db.query(Comment).filter_by(id=comment_id).first()
    if not comment:
        # Return an empty list instead of raising a 404 error
        return []

    # Retrieve attachments for the comment
    attachments = db.query(ActiveStorageAttachment).filter_by(
        record_id=comment_id, record_type='Comment', name='photos'
    ).all()

    photos = []

    for attachment in attachments:
        # Retrieve the associated blob for each attachment
        blob = db.query(ActiveStorageBlob).filter_by(id=attachment.blob_id).first()

        if not blob:
            continue  # Skip if no blob found

        # Generate a SAS token for the blob
        try:
            sas_token = generate_blob_sas(
                account_name=account_name,
                container_name=CONTAINER_NAME,
                blob_name=blob.key,
                account_key=account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=1)  # Token valid for 1 hour
            )
        except Exception as e:
            logger.error(f"Error generating SAS token for blob {blob.key}: {e}")
            continue  # Skip this blob if there's an error

        # Construct the secure URL with SAS token
        blob_url = f"https://{account_name}.blob.core.windows.net/{CONTAINER_NAME}/{blob.key}?{sas_token}"

        # Append the photo details to the list
        photos.append({
            "filename": blob.filename,
            "content_type": blob.content_type,
            "url": blob_url,
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

# Comments for a specific Unit
@router.get("/comments/unit/{unit_id}", response_model=List[CommentResponse])
def get_comments_by_unit(unit_id: int, db: Session = Depends(get_db)):
    comments = db.query(Comment).filter(Comment.unit_id == unit_id).order_by(Comment.created_at.desc()).all()
    # Return empty list if no comments
    if not comments:
        return []
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    comment_responses = []
    for comment in comments:
        user = db.query(User).filter(User.id == comment.user_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        comment_responses.append(CommentResponse(
            id=comment.id,
            content=comment.content,
            user_id=comment.user_id,
            address_id=comment.address_id,  # <-- Ensure address_id is included
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
            unit=UnitResponse(
                id=unit.id,
                number=unit.number,
                address_id=unit.address_id,
                created_at=unit.created_at,
                updated_at=unit.updated_at
            ) if unit else None,
            created_at=comment.created_at,
            updated_at=comment.updated_at
        ))
    return comment_responses

