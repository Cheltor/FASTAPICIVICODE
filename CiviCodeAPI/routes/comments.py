from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Body
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta
from typing import List, Optional
from models import Comment, ContactComment, ActiveStorageAttachment, ActiveStorageBlob, User, Unit
from schemas import (
    CommentCreate,
    CommentResponse,
    ContactCommentCreate,
    ContactCommentResponse,
    UserResponse,
    UnitResponse,
)
from database import get_db
from models import Mention
import storage
from image_utils import normalize_image_for_web
from media_service import ensure_blob_browser_safe
import os
import logging
import uuid
import jwt
import re
from email_service import send_notification_email

router = APIRouter()
@router.get("/comments/{comment_id}/mentions", response_model=List[UserResponse])
def get_comment_mentions(comment_id: int, db: Session = Depends(get_db)):
    """Return the list of users mentioned in a given comment."""
    mentions = (
        db.query(User)
        .join(Mention, Mention.user_id == User.id)
        .filter(Mention.comment_id == comment_id)
        .all()
    )
    return mentions

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Ensure Azure storage lazy clients are initialized before using account info
def _ensure_storage_init() -> None:
    _ = storage.blob_service_client  # Touch to trigger lazy init and set account_name/account_key

# Auth: Admin-only guard
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")
SECRET_KEY = "trpdds2020"
ALGORITHM = "HS256"

def _require_admin(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid auth token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if int(getattr(user, 'role', 0)) < 3:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

# Get all comments (augmented with address combadd and user)
@router.get("/comments/", response_model=List[CommentResponse])
def get_comments(skip: int = 0, db: Session = Depends(get_db)):
    comments = db.query(Comment).order_by(Comment.created_at.desc()).offset(skip).all()
    results: List[CommentResponse] = []
    for c in comments:
        user = db.query(User).filter(User.id == c.user_id).first()
        combadd = None
        # Lazy load combadd via address_id to avoid heavy join
        try:
            from models import Address
            addr = db.query(Address).filter(Address.id == c.address_id).first()
            combadd = addr.combadd if addr else None
        except Exception:
            combadd = None
        results.append(CommentResponse(
            id=c.id,
            content=c.content,
            user_id=c.user_id,
            address_id=c.address_id,
            user=UserResponse.from_orm(user) if user else None,
            unit_id=c.unit_id,
            combadd=combadd,
            created_at=c.created_at,
            updated_at=c.updated_at,
        ))
    return results

# Get all contact comments (admin list)
@router.get("/comments/contact/", response_model=List[ContactCommentResponse])
def get_all_contact_comments(skip: int = 0, db: Session = Depends(get_db)):
    comments = db.query(ContactComment).order_by(ContactComment.created_at.desc()).offset(skip).all()
    return comments

# Update a comment by ID
@router.put("/comments/{comment_id}", response_model=CommentResponse)
def update_comment(comment_id: int, comment_in: CommentCreate, db: Session = Depends(get_db), admin_user: User = Depends(_require_admin)):
    db_comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Update fields from schema; allow clearing fields with empty strings
    data = comment_in.dict()
    for key, value in data.items():
        setattr(db_comment, key, value if value != '' else None)

    db.commit()
    db.refresh(db_comment)
    return db_comment

# Delete a comment by ID
@router.delete("/comments/{comment_id}", status_code=204)
def delete_comment(comment_id: int, db: Session = Depends(get_db), admin_user: User = Depends(_require_admin)):
    db_comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    try:
        db.delete(db_comment)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Unable to delete comment due to related records")

# Create a new comment (JSON payload, no files)
@router.post("/comments/", response_model=CommentResponse)
def create_comment(comment: CommentCreate, db: Session = Depends(get_db)):
    logger.debug(f"Received payload: {comment.dict()}")
    logger.debug(f"Creating comment with content: {comment.content}, user_id: {comment.user_id}, unit_id: {comment.unit_id}")
    new_comment = Comment(**comment.dict())
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    # Detect @username mentions and create notifications
    try:
        MENTION_RE = re.compile(r"@([A-Za-z0-9@._-]+)")
        usernames = set(MENTION_RE.findall(new_comment.content or ""))
        if usernames:
            users = db.query(User).filter(User.name.in_(list(usernames))).all()
            for u in users:
                if u.id == new_comment.user_id:
                    continue
                # Create Notification for existing notifications table
                try:
                    notif = None
                    from models import Notification, Mention
                    notif = Notification(
                        title=f"You were mentioned",
                        body=f"You were mentioned in a comment: {new_comment.content[:200]}",
                        comment_id=new_comment.id,
                        user_id=int(u.id),
                        read=False,
                    )
                    db.add(notif)
                    db.commit()
                except Exception:
                    db.rollback()
                # Create Mention row
                try:
                    m = Mention(comment_id=new_comment.id, user_id=int(u.id), actor_id=new_comment.user_id)
                    db.add(m)
                    db.commit()
                except Exception:
                    db.rollback()
                # Send email (best effort)
                try:
                    target_email = u.email
                    if target_email:
                        send_notification_email(subject="You were mentioned", body=new_comment.content, to_email=target_email, inspection_id=None)
                except Exception:
                    pass
    except Exception:
        # don't let mention handling break comment creation
        pass
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

# Get a single ContactComment by ID (for admin editor)
@router.get("/comments/contact/by-id/{comment_id}", response_model=ContactCommentResponse)
def get_contact_comment(comment_id: int, db: Session = Depends(get_db)):
    cc = db.query(ContactComment).filter(ContactComment.id == comment_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="ContactComment not found")
    return cc

# Update a ContactComment (edit the comment text)
@router.put("/comments/contact/{comment_id}", response_model=ContactCommentResponse)
def update_contact_comment(comment_id: int, data: dict = Body(...), db: Session = Depends(get_db), admin_user: User = Depends(_require_admin)):
    cc = db.query(ContactComment).filter(ContactComment.id == comment_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="ContactComment not found")
    # Update only the editable fields; currently 'comment' is primary
    payload = data if isinstance(data, dict) else {}
    comment_text = payload.get('comment')
    if comment_text is not None:
        cc.comment = comment_text
    # Optionally update the author (user_id) if provided
    if 'user_id' in payload and payload['user_id'] is not None:
        new_user = db.query(User).filter(User.id == int(payload['user_id'])).first()
        if not new_user:
            raise HTTPException(status_code=404, detail="Target user not found")
        cc.user_id = int(payload['user_id'])
    # Optionally allow updating user_id or contact_id if your schema demands; typically we don't change ownership
    db.add(cc)
    db.commit()
    db.refresh(cc)
    return cc

# Delete a ContactComment (admin-only)
@router.delete("/comments/contact/{comment_id}", status_code=204)
def delete_contact_comment(comment_id: int, db: Session = Depends(get_db), admin_user: User = Depends(_require_admin)):
    cc = db.query(ContactComment).filter(ContactComment.id == comment_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="ContactComment not found")
    try:
        db.delete(cc)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Unable to delete contact comment due to related records")

# Fetch Comment photo by ID
@router.get("/comments/{comment_id}/photos")
def get_comment_photos(comment_id: int, download: bool = False, db: Session = Depends(get_db)):
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

        # Ensure browser-safe; convert on-demand if needed
        try:
            blob = ensure_blob_browser_safe(db, blob)
        except Exception as e:
            logger.error(f"On-demand conversion failed for blob {getattr(blob, 'key', '?')}: {e}")

            # Generate a SAS token for the blob
        try:
            sas_token = generate_blob_sas(
                account_name=storage.account_name,
                container_name=storage.CONTAINER_NAME,
                blob_name=blob.key,
                account_key=storage.account_key,
                permission=BlobSasPermissions(read=True),
                start=datetime.utcnow() - timedelta(minutes=5),  # Allow for clock skew
                expiry=datetime.utcnow() + timedelta(hours=1),  # Token valid for 1 hour
                content_disposition=(f'attachment; filename="{blob.filename}"' if download else None),
            )
        except Exception as e:
            logger.error(f"Error generating SAS token for blob {blob.key}: {e}")
            continue  # Skip this blob if there's an error

        # Construct the secure URL with SAS token
        blob_url = f"https://{storage.account_name}.blob.core.windows.net/{storage.CONTAINER_NAME}/{blob.key}?{sas_token}"
        poster_url = None
        if (blob.content_type or "").startswith("video/") and blob.key.lower().endswith('.mp4'):
            base = blob.key[:-4]
            poster_key = f"{base}-poster.jpg"
            try:
                _ensure_storage_init()
                poster_sas = generate_blob_sas(
                    account_name=storage.account_name,
                    container_name=storage.CONTAINER_NAME,
                    blob_name=poster_key,
                    account_key=storage.account_key,
                    permission=BlobSasPermissions(read=True),
                    start=datetime.utcnow() - timedelta(minutes=5),
                    expiry=datetime.utcnow() + timedelta(hours=1),
                )
                poster_url = f"https://{storage.account_name}.blob.core.windows.net/{storage.CONTAINER_NAME}/{poster_key}?{poster_sas}"
            except Exception:
                poster_url = None

        # Append the photo details to the list
        photos.append({
            "filename": blob.filename,
            "content_type": blob.content_type,
            "url": blob_url,
            "poster_url": poster_url,
        })

    return photos
 
# Create a new comment for an Address, with optional file attachments
@router.post("/comments/{address_id}/address/", response_model=CommentResponse)
@router.post("/comments/{address_id}/address", response_model=CommentResponse)
async def create_address_comment(
    address_id: int,
    content: str = Form(...),
    user_id: int = Form(...),
    unit_id: Optional[int] = Form(None),
    mentioned_user_ids: Optional[str] = Form(None),
    files: List[UploadFile] = File([]),
    db: Session = Depends(get_db),
):
    new_comment = Comment(content=content, user_id=user_id, address_id=address_id, unit_id=unit_id)
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    # Detect mentions in form-based comment (prefer explicit ids from frontend)
    try:
        from models import Notification, Mention
        ids: set[int] = set()
        if mentioned_user_ids:
            for part in str(mentioned_user_ids).split(','):
                try:
                    val = int(part.strip())
                    if val:
                        ids.add(val)
                except Exception:
                    continue
        if not ids:
            # fallback to parsing @names if ids not provided
            MENTION_RE = re.compile(r"@([A-Za-z0-9@._\- ]+)")
            usernames = set(MENTION_RE.findall(content or ""))
            if usernames:
                users = db.query(User).filter(User.name.in_(list(usernames))).all()
                ids = {int(u.id) for u in users}

        for uid in ids:
            if uid == user_id:
                continue
            try:
                notif = Notification(
                    title=f"You were mentioned",
                    body=f"You were mentioned in a comment: {content[:200]}",
                    comment_id=new_comment.id,
                    user_id=int(uid),
                    read=False,
                )
                db.add(notif)
                db.commit()
            except Exception:
                db.rollback()
            try:
                m = Mention(comment_id=new_comment.id, user_id=int(uid), actor_id=user_id)
                db.add(m)
                db.commit()
            except Exception:
                db.rollback()
            try:
                u = db.query(User).filter(User.id == int(uid)).first()
                if u and u.email:
                    send_notification_email(subject="You were mentioned", body=content, to_email=u.email, inspection_id=None)
            except Exception:
                pass
    except Exception:
        pass

    for file in files:
        try:
            raw_bytes = await file.read()
            normalized_bytes, norm_filename, norm_ct = normalize_image_for_web(raw_bytes, file.filename, file.content_type)
            blob_key = f"address-comments/{new_comment.id}/{uuid.uuid4()}-{norm_filename}"
            blob_client = storage.blob_service_client.get_blob_client(container=storage.CONTAINER_NAME, blob=blob_key)
            blob_client.upload_blob(normalized_bytes, overwrite=True, content_type=norm_ct)

            blob_row = ActiveStorageBlob(
                key=blob_key,
                filename=norm_filename,
                content_type=norm_ct,
                meta_data=None,
                service_name="azure",
                byte_size=len(normalized_bytes),
                checksum=None,
                created_at=datetime.utcnow(),
            )
            db.add(blob_row)
            db.commit()
            db.refresh(blob_row)

            attachment_row = ActiveStorageAttachment(
                name="photos",  # align with get_comment_photos name
                record_type="Comment",
                record_id=new_comment.id,
                blob_id=blob_row.id,
                created_at=datetime.utcnow(),
            )
            db.add(attachment_row)
            db.commit()
        except Exception as e:
            logging.exception(f"Failed to upload attachment for Comment {new_comment.id}: {e}")
            continue

    # Build a full response including user and optional unit to match CommentResponse
    user = db.query(User).filter(User.id == new_comment.user_id).first()
    unit = None
    if new_comment.unit_id:
        unit = db.query(Unit).filter(Unit.id == new_comment.unit_id).first()

    return CommentResponse(
        id=new_comment.id,
        content=new_comment.content,
        user_id=new_comment.user_id,
        address_id=new_comment.address_id,
        user=UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            phone=user.phone,
            role=user.role,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ) if user else None,
        unit_id=new_comment.unit_id,
        unit=UnitResponse(
            id=unit.id,
            number=unit.number,
            address_id=unit.address_id,
            created_at=unit.created_at,
            updated_at=unit.updated_at,
        ) if unit else None,
        created_at=new_comment.created_at,
        updated_at=new_comment.updated_at,
    )
    
# Create a new comment for a Contact, with optional file attachments
@router.post("/comments/{contact_id}/contact/", response_model=ContactCommentResponse)
@router.post("/comments/{contact_id}/contact", response_model=ContactCommentResponse)
async def create_contact_comment(
    contact_id: int,
    comment: str = Form(...),
    user_id: int = Form(...),
    mentioned_user_ids: Optional[str] = Form(None),
    files: List[UploadFile] = File([]),
    db: Session = Depends(get_db),
):
    # Persist the contact comment first
    new_comment = ContactComment(comment=comment, user_id=user_id, contact_id=contact_id)
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    # Detect mentions in contact comment (prefer explicit ids from frontend)
    try:
        from models import Notification, Mention
        ids: set[int] = set()
        if mentioned_user_ids:
            for part in str(mentioned_user_ids).split(','):
                try:
                    val = int(part.strip())
                    if val:
                        ids.add(val)
                except Exception:
                    continue
        if not ids:
            MENTION_RE = re.compile(r"@([A-Za-z0-9@._\- ]+)")
            usernames = set(MENTION_RE.findall(comment or ""))
            if usernames:
                users = db.query(User).filter(User.name.in_(list(usernames))).all()
                ids = {int(u.id) for u in users}

        for uid in ids:
            if uid == user_id:
                continue
            try:
                notif = Notification(
                    title=f"You were mentioned",
                    body=f"You were mentioned in a contact comment: {comment[:200]}",
                    comment_id=new_comment.id,
                    user_id=int(uid),
                    read=False,
                )
                db.add(notif)
                db.commit()
            except Exception:
                db.rollback()
            try:
                m = Mention(comment_id=new_comment.id, user_id=int(uid), actor_id=user_id)
                db.add(m)
                db.commit()
            except Exception:
                db.rollback()
            try:
                u = db.query(User).filter(User.id == int(uid)).first()
                if u and u.email:
                    send_notification_email(subject="You were mentioned", body=comment, to_email=u.email, inspection_id=None)
            except Exception:
                pass
    except Exception:
        pass

    # Upload any attachments and create ActiveStorage records
    for file in files:
        try:
            raw = await file.read()
            normalized_bytes, norm_filename, norm_ct = normalize_image_for_web(raw, file.filename, file.content_type)
            blob_key = f"contact-comments/{new_comment.id}/{uuid.uuid4()}-{norm_filename}"
            blob_client = storage.blob_service_client.get_blob_client(container=storage.CONTAINER_NAME, blob=blob_key)
            blob_client.upload_blob(normalized_bytes, overwrite=True, content_type=norm_ct)

            # Create ActiveStorageBlob entry
            blob_row = ActiveStorageBlob(
                key=blob_key,
                filename=norm_filename,
                content_type=norm_ct,
                meta_data=None,
                service_name="azure",
                byte_size=len(normalized_bytes),
                checksum=None,
                created_at=datetime.utcnow(),
            )
            db.add(blob_row)
            db.commit()
            db.refresh(blob_row)

            # Create ActiveStorageAttachment entry linking to the ContactComment
            attachment_row = ActiveStorageAttachment(
                name="attachments",
                record_type="ContactComment",
                record_id=new_comment.id,
                blob_id=blob_row.id,
                created_at=datetime.utcnow(),
            )
            db.add(attachment_row)
            db.commit()
        except Exception as e:
            logging.exception(f"Failed to upload attachment for ContactComment {new_comment.id}: {e}")
            # Don't fail the entire request due to one bad file; continue
            continue

    return new_comment

@router.get("/comments/contact/{comment_id}/attachments")
def get_contact_comment_attachments(comment_id: int, download: bool = False, db: Session = Depends(get_db)):
    """Return signed URLs for attachments on a ContactComment."""
    # Ensure the comment exists
    contact_comment = db.query(ContactComment).filter(ContactComment.id == comment_id).first()
    if not contact_comment:
        raise HTTPException(status_code=404, detail="ContactComment not found")

    attachments = db.query(ActiveStorageAttachment).filter_by(
        record_id=comment_id, record_type="ContactComment", name="attachments"
    ).all()

    results = []
    for attachment in attachments:
        blob = db.query(ActiveStorageBlob).filter_by(id=attachment.blob_id).first()
        if not blob:
            continue
        try:
            _ensure_storage_init()
            sas_token = generate_blob_sas(
                account_name=storage.account_name,
                container_name=storage.CONTAINER_NAME,
                blob_name=blob.key,
                account_key=storage.account_key,
                permission=BlobSasPermissions(read=True),
                start=datetime.utcnow() - timedelta(minutes=5),  # Allow for clock skew
                expiry=datetime.utcnow() + timedelta(hours=1),
                content_disposition=(f'attachment; filename="{blob.filename}"' if download else None),
            )
            url = f"https://{storage.account_name}.blob.core.windows.net/{storage.CONTAINER_NAME}/{blob.key}?{sas_token}"
            results.append({
                "filename": blob.filename,
                "content_type": blob.content_type,
                "url": url,
            })
        except Exception as e:
            logging.exception(f"Failed generating SAS for blob {blob.key}: {e}")
            continue

    return results

@router.get("/comments/contact/{comment_id}/attachments/count")
def get_contact_comment_attachment_count(comment_id: int, db: Session = Depends(get_db)):
    """Return the number of attachments for a ContactComment without generating SAS URLs."""
    contact_comment = db.query(ContactComment).filter(ContactComment.id == comment_id).first()
    if not contact_comment:
        raise HTTPException(status_code=404, detail="ContactComment not found")

    count = db.query(ActiveStorageAttachment).filter_by(
        record_id=comment_id, record_type="ContactComment", name="attachments"
    ).count()

    return {"count": count}

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

# Create a new comment for a Unit, with optional file attachments
@router.post("/comments/unit/{unit_id}/", response_model=CommentResponse)
@router.post("/comments/unit/{unit_id}", response_model=CommentResponse)
async def create_unit_comment(
    unit_id: int,
    address_id: int = Form(...),
    content: str = Form(...),
    user_id: int = Form(...),
    files: List[UploadFile] = File([]),
    db: Session = Depends(get_db),
):
    new_comment = Comment(content=content, user_id=user_id, address_id=address_id, unit_id=unit_id)
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    for file in files:
        try:
            raw_bytes = await file.read()
            normalized_bytes, norm_filename, norm_ct = normalize_image_for_web(raw_bytes, file.filename, file.content_type)
            blob_key = f"unit-comments/{new_comment.id}/{uuid.uuid4()}-{norm_filename}"
            blob_client = storage.blob_service_client.get_blob_client(container=storage.CONTAINER_NAME, blob=blob_key)
            blob_client.upload_blob(normalized_bytes, overwrite=True, content_type=norm_ct)

            blob_row = ActiveStorageBlob(
                key=blob_key,
                filename=norm_filename,
                content_type=norm_ct,
                meta_data=None,
                service_name="azure",
                byte_size=len(normalized_bytes),
                checksum=None,
                created_at=datetime.utcnow(),
            )
            db.add(blob_row)
            db.commit()
            db.refresh(blob_row)

            attachment_row = ActiveStorageAttachment(
                name="photos",  # align with get_comment_photos name
                record_type="Comment",
                record_id=new_comment.id,
                blob_id=blob_row.id,
                created_at=datetime.utcnow(),
            )
            db.add(attachment_row)
            db.commit()
        except Exception as e:
            logging.exception(f"Failed to upload attachment for Unit Comment {new_comment.id}: {e}")
            continue

    # Build a full response including user and optional unit to match CommentResponse
    user = db.query(User).filter(User.id == new_comment.user_id).first()
    unit = db.query(Unit).filter(Unit.id == unit_id).first()

    return CommentResponse(
        id=new_comment.id,
        content=new_comment.content,
        user_id=new_comment.user_id,
        address_id=new_comment.address_id,
        user=UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            phone=user.phone,
            role=user.role,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ) if user else None,
        unit_id=unit_id,
        unit=UnitResponse(
            id=unit.id,
            number=unit.number,
            address_id=unit.address_id,
            created_at=unit.created_at,
            updated_at=unit.updated_at,
        ) if unit else None,
        created_at=new_comment.created_at,
        updated_at=new_comment.updated_at,
    )

# Update a unit comment (admin-only)
@router.put("/comments/unit/{comment_id}", response_model=CommentResponse)
def update_unit_comment(comment_id: int, comment_in: CommentCreate, db: Session = Depends(get_db), admin_user: User = Depends(_require_admin)):
    db_comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    data = comment_in.dict()
    for key, value in data.items():
        setattr(db_comment, key, value if value != '' else None)
    db.commit()
    db.refresh(db_comment)
    return db_comment

# Delete a unit comment (admin-only)
@router.delete("/comments/unit/{comment_id}", status_code=204)
def delete_unit_comment(comment_id: int, db: Session = Depends(get_db), admin_user: User = Depends(_require_admin)):
    db_comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    try:
        db.delete(db_comment)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Unable to delete comment due to related records")

