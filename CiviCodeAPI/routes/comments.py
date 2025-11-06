from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Body, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta
from typing import List, Optional, Union
from models import Comment, ContactComment, ActiveStorageAttachment, ActiveStorageBlob, User, Unit, Contact, CommentContactLink, Mention
from schemas import (
    CommentCreate,
    CommentResponse,
    ContactCommentCreate,
    ContactCommentResponse,
    ContactResponse,
    UserResponse,
    UnitResponse,
    CommentPageResponse,
    ViolationResponse,
    ViolationFromCommentRequest,
)
from database import get_db
import storage
from image_utils import normalize_image_for_web
from media_service import ensure_blob_browser_safe
import os
import logging
import uuid
import jwt
import re
import models
from email_service import send_notification_email

USER_MENTION_RE = re.compile(r"@([A-Za-z0-9@._\- ]+)")
CONTACT_MENTION_RE = re.compile(r"%([A-Za-z0-9@._\- ]+)")


def _parse_id_values(raw) -> set[int]:
    ids: set[int] = set()
    if raw is None:
        return ids
    if isinstance(raw, (list, tuple, set)):
        iterable = raw
    else:
        cleaned = str(raw).replace(';', ',')
        iterable = cleaned.split(',')
    for part in iterable:
        try:
            val = int(str(part).strip())
            if val:
                ids.add(val)
        except Exception:
            continue
    return ids


def _collect_user_ids(db: Session, raw_ids, content: Optional[str]) -> set[int]:
    ids = _parse_id_values(raw_ids)
    if ids:
        return ids
    tokens = {token.strip() for token in USER_MENTION_RE.findall(content or '') if token and token.strip()}
    if not tokens:
        return set()
    users = db.query(User).filter(User.name.in_(list(tokens))).all()
    return {int(u.id) for u in users}


def _collect_contact_ids(db: Session, raw_ids, content: Optional[str]) -> set[int]:
    ids = _parse_id_values(raw_ids)
    if ids:
        return ids
    tokens = {token.strip() for token in CONTACT_MENTION_RE.findall(content or '') if token and token.strip()}
    if not tokens:
        return set()
    contacts = db.query(Contact).filter(Contact.name.in_(list(tokens))).all()
    return {int(c.id) for c in contacts}


def _store_contact_mentions(db: Session, comment_id: int, actor_id: Optional[int], contact_ids: set[int]) -> None:
    if not contact_ids:
        return
    try:
        existing_ids = {
            int(link.contact_id)
            for link in db.query(CommentContactLink).filter(CommentContactLink.comment_id == comment_id)
        }
        for cid in contact_ids:
            if cid in existing_ids:
                continue
            db.add(CommentContactLink(comment_id=comment_id, contact_id=cid, actor_id=actor_id))
        db.commit()
    except Exception:
        db.rollback()


def _get_contact_mentions(db: Session, comment_id: int) -> List[Contact]:
    try:
        return (
            db.query(Contact)
            .join(CommentContactLink, CommentContactLink.contact_id == Contact.id)
            .filter(CommentContactLink.comment_id == comment_id)
            .all()
        )
    except Exception:
        return []


def _handle_user_mentions(
    db: Session,
    comment_id: int,
    actor_id: Optional[int],
    content: Optional[str],
    raw_ids,
    context_label: str,
    inspection_id: Optional[int] = None,
) -> None:
    try:
        from models import Notification

        ids = _collect_user_ids(db, raw_ids, content)
        if not ids:
            return
        snippet = (content or '')[:200]
        for uid in ids:
            if actor_id is not None and uid == actor_id:
                try:
                    m = Mention(comment_id=comment_id, user_id=int(uid), actor_id=actor_id)
                    db.add(m)
                    db.commit()
                except Exception:
                    db.rollback()
                continue
            try:
                notif = Notification(
                    title="You were mentioned",
                    body=f"You were mentioned in a {context_label}: {snippet}",
                    comment_id=comment_id,
                    inspection_id=inspection_id,
                    user_id=int(uid),
                    read=False,
                )
                db.add(notif)
                db.commit()
            except Exception:
                db.rollback()
            try:
                m = Mention(comment_id=comment_id, user_id=int(uid), actor_id=actor_id)
                db.add(m)
                db.commit()
            except Exception:
                db.rollback()
            try:
                user = db.query(User).filter(User.id == int(uid)).first()
                if user and user.email:
                    send_notification_email(subject="You were mentioned", body=snippet, to_email=user.email, inspection_id=inspection_id)
            except Exception:
                pass
    except Exception:
        # Mention handling should not break primary flow
        pass


def _build_comment_response(db: Session, comment: Comment) -> CommentResponse:
    user = db.query(User).filter(User.id == comment.user_id).first() if comment.user_id else None
    unit = db.query(Unit).filter(Unit.id == comment.unit_id).first() if comment.unit_id else None

    combadd = None
    if comment.address_id:
        try:
            from models import Address
            address = db.query(Address).filter(Address.id == comment.address_id).first()
            combadd = address.combadd if address else None
        except Exception:
            combadd = None

    try:
        user_mentions = (
            db.query(User)
            .join(Mention, Mention.user_id == User.id)
            .filter(Mention.comment_id == comment.id)
            .all()
        )
    except Exception:
        user_mentions = []

    contact_mentions = _get_contact_mentions(db, comment.id)

    return CommentResponse(
        id=comment.id,
        content=comment.content,
        user_id=comment.user_id,
        address_id=comment.address_id,
        user=UserResponse.from_orm(user) if user else None,
        unit_id=comment.unit_id,
        unit=UnitResponse.from_orm(unit) if unit else None,
        combadd=combadd,
        mentions=[UserResponse.from_orm(u) for u in user_mentions] if user_mentions else None,
        contact_mentions=[ContactResponse.from_orm(c) for c in contact_mentions] if contact_mentions else None,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )

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


@router.post("/comments/{comment_id}/violations", response_model=ViolationResponse)
def create_violation_from_comment(
    comment_id: int,
    payload: ViolationFromCommentRequest = Body(...),
    db: Session = Depends(get_db),
):
    """Create a violation pre-populated with data copied from a comment."""

    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if not comment.address_id:
        raise HTTPException(status_code=400, detail="Comment is not associated with an address")

    deadline = payload.deadline
    if not deadline:
        raise HTTPException(status_code=400, detail="Deadline is required to create a violation")

    user_id = payload.user_id or comment.user_id
    if not user_id:
        raise HTTPException(status_code=400, detail="A violation assignee is required")

    violation = models.Violation(
        address_id=comment.address_id,
        user_id=user_id,
        unit_id=comment.unit_id,
        deadline=deadline,
        violation_type=payload.violation_type or "doorhanger",
        status=payload.status if payload.status is not None else 0,
        description=payload.description if payload.description is not None else comment.content,
        comment=payload.comment if payload.comment is not None else comment.content,
    )

    try:
        db.add(violation)
        db.flush()

        if payload.codes:
            codes = db.query(models.Code).filter(models.Code.id.in_(payload.codes)).all()
            violation.codes = codes

        attachments = (
            db.query(ActiveStorageAttachment)
            .filter(
                ActiveStorageAttachment.record_type == "Comment",
                ActiveStorageAttachment.record_id == comment_id,
                ActiveStorageAttachment.name == "photos",
            )
            .all()
        )

        for attachment in attachments:
            db.add(
                ActiveStorageAttachment(
                    name="photos",
                    record_type="Violation",
                    record_id=violation.id,
                    blob_id=attachment.blob_id,
                    created_at=datetime.utcnow(),
                )
            )

        db.commit()
    except Exception as exc:
        db.rollback()
        logging.exception("Failed to create violation from comment %s: %s", comment_id, exc)
        raise HTTPException(status_code=500, detail="Failed to create violation from comment")

    db.refresh(violation)
    return violation

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Ensure Azure storage lazy clients are initialized before using account info
def _ensure_storage_init() -> None:
    storage.ensure_initialized()

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

# Get recent comments with optional pagination; batches related data to avoid N+1
@router.get("/comments/", response_model=List[CommentResponse])
def get_comments(skip: int = 0, limit: int = 200, db: Session = Depends(get_db)):
    # Pull a page of comments in newest-first order
    q = db.query(Comment).order_by(Comment.created_at.desc())
    if skip:
        q = q.offset(skip)
    if limit:
        q = q.limit(limit)
    comments = q.all()

    if not comments:
        return []

    # Gather unique ids for batch lookups
    user_ids = {int(c.user_id) for c in comments if c.user_id is not None}
    address_ids = {int(c.address_id) for c in comments if c.address_id is not None}
    comment_ids = {int(c.id) for c in comments}

    # Batch fetch related users
    users_by_id = {}
    if user_ids:
        for u in db.query(User).filter(User.id.in_(list(user_ids))).all():
            users_by_id[int(u.id)] = u

    # Batch fetch address combadd
    combadd_by_address_id = {}
    if address_ids:
        try:
            from models import Address
            for addr in db.query(Address).filter(Address.id.in_(list(address_ids))).all():
                combadd_by_address_id[int(addr.id)] = addr.combadd
        except Exception:
            combadd_by_address_id = {}

    # Batch fetch mentions -> list of UserResponse per comment
    mentions_by_comment: dict[int, list[User]] = {cid: [] for cid in comment_ids}
    try:
        if comment_ids:
            # Join to users so the frontend doesn't need to refetch
            rows = (
                db.query(User, Mention)
                .join(Mention, Mention.user_id == User.id)
                .filter(Mention.comment_id.in_(list(comment_ids)))
                .all()
            )
            for u, m in rows:
                mentions_by_comment[int(m.comment_id)].append(u)
    except Exception:
        pass

    contact_mentions_by_comment: dict[int, list[Contact]] = {cid: [] for cid in comment_ids}
    try:
        if comment_ids:
            contact_rows = (
                db.query(Contact, CommentContactLink)
                .join(CommentContactLink, CommentContactLink.contact_id == Contact.id)
                .filter(CommentContactLink.comment_id.in_(list(comment_ids)))
                .all()
            )
            for contact, link in contact_rows:
                contact_mentions_by_comment[int(link.comment_id)].append(contact)
    except Exception:
        pass

    # Build responses
    results: List[CommentResponse] = []
    for c in comments:
        user = users_by_id.get(int(c.user_id)) if c.user_id is not None else None
        combadd = combadd_by_address_id.get(int(c.address_id)) if c.address_id is not None else None
        mentions_users = mentions_by_comment.get(int(c.id), [])
        contact_mentions = contact_mentions_by_comment.get(int(c.id), [])
        results.append(CommentResponse(
            id=c.id,
            content=c.content,
            user_id=c.user_id,
            address_id=c.address_id,
            user=UserResponse.from_orm(user) if user else None,
            unit_id=c.unit_id,
            combadd=combadd,
            mentions=[UserResponse.from_orm(u) for u in mentions_users] if mentions_users else None,
            contact_mentions=[ContactResponse.from_orm(ct) for ct in contact_mentions] if contact_mentions else None,
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
def create_comment(
    comment: CommentCreate,
    mentioned_user_ids: Optional[List[int]] = Body(default=None),
    mentioned_contact_ids: Optional[List[int]] = Body(default=None),
    db: Session = Depends(get_db),
):
    logger.debug(f"Received payload: {comment.dict()}")
    logger.debug(f"Creating comment with content: {comment.content}, user_id: {comment.user_id}, unit_id: {comment.unit_id}")
    new_comment = Comment(**comment.dict())
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    _handle_user_mentions(
        db=db,
        comment_id=new_comment.id,
        actor_id=new_comment.user_id,
        content=new_comment.content,
        raw_ids=mentioned_user_ids,
        context_label="comment",
    )

    contact_ids = _collect_contact_ids(db, mentioned_contact_ids, new_comment.content)
    if contact_ids:
        _store_contact_mentions(db, new_comment.id, new_comment.user_id, contact_ids)

    logger.debug(f"Created comment with ID: {new_comment.id}, unit_id: {new_comment.unit_id}")
    return _build_comment_response(db, new_comment)

# Get all comments for a specific Address
@router.get(
    "/comments/address/{address_id}",
    response_model=Union[CommentPageResponse, List[CommentResponse]],
)
def get_comments_by_address(
    address_id: int,
    page: Optional[int] = Query(None, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    base_query = (
        db.query(Comment)
        .filter(Comment.address_id == address_id)
        .order_by(Comment.created_at.desc())
    )

    if page is None:
        comments = base_query.all()
        return [_build_comment_response(db, comment) for comment in comments]

    total = base_query.count()
    offset = (page - 1) * page_size
    comments = base_query.offset(offset).limit(page_size).all()
    results = [_build_comment_response(db, comment) for comment in comments]
    has_more = (offset + len(results)) < total
    return CommentPageResponse(
        results=results,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )

# Get all comments for a specific Contact
@router.get("/comments/contact/{contact_id}", response_model=List[ContactCommentResponse])
def get_comments_by_contact(contact_id: int, db: Session = Depends(get_db)):
    if contact_id is None:
        raise HTTPException(status_code=422, detail="Invalid contact_id")
    comments = db.query(ContactComment).filter(ContactComment.contact_id == contact_id).order_by(ContactComment.created_at.desc()).all()
    return comments


@router.get("/comments/contact/{contact_id}/mentioned", response_model=List[CommentResponse])
def get_comments_mentioning_contact(contact_id: int, db: Session = Depends(get_db)):
    if contact_id is None:
        raise HTTPException(status_code=422, detail="Invalid contact_id")
    linked_comments = (
        db.query(Comment)
        .join(CommentContactLink, CommentContactLink.comment_id == Comment.id)
        .filter(CommentContactLink.contact_id == contact_id)
        .order_by(Comment.created_at.desc())
        .all()
    )
    return [_build_comment_response(db, comment) for comment in linked_comments]

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
    mentioned_contact_ids: Optional[str] = Form(None),
    files: List[UploadFile] = File([]),
    db: Session = Depends(get_db),
):
    new_comment = Comment(content=content, user_id=user_id, address_id=address_id, unit_id=unit_id)
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    _handle_user_mentions(
        db=db,
        comment_id=new_comment.id,
        actor_id=user_id,
        content=content,
        raw_ids=mentioned_user_ids,
        context_label="comment",
    )

    contact_ids = _collect_contact_ids(db, mentioned_contact_ids, content)
    if contact_ids:
        _store_contact_mentions(db, new_comment.id, user_id, contact_ids)

    if files:
        _ensure_storage_init()

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
    # Fetch mentions to include in the response
    try:
        mentions_users = (
            db.query(User)
            .join(Mention, Mention.user_id == User.id)
            .filter(Mention.comment_id == new_comment.id)
            .all()
        )
    except Exception:
        mentions_users = []
    contact_mentions = _get_contact_mentions(db, new_comment.id)

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
        mentions=[UserResponse.from_orm(u) for u in mentions_users] if mentions_users else None,
        contact_mentions=[ContactResponse.from_orm(c) for c in contact_mentions] if contact_mentions else None,
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
                # Save self mention but skip notification/email
                try:
                    m = Mention(comment_id=new_comment.id, user_id=int(uid), actor_id=user_id)
                    db.add(m)
                    db.commit()
                except Exception:
                    db.rollback()
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
    if files:
        _ensure_storage_init()

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
    mentioned_user_ids: Optional[str] = Form(None),
    mentioned_contact_ids: Optional[str] = Form(None),
    files: List[UploadFile] = File([]),
    db: Session = Depends(get_db),
):
    new_comment = Comment(content=content, user_id=user_id, address_id=address_id, unit_id=unit_id)
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    _handle_user_mentions(
        db=db,
        comment_id=new_comment.id,
        actor_id=user_id,
        content=content,
        raw_ids=mentioned_user_ids,
        context_label="unit comment",
    )

    contact_ids = _collect_contact_ids(db, mentioned_contact_ids, content)
    if contact_ids:
        _store_contact_mentions(db, new_comment.id, user_id, contact_ids)

    if files:
        _ensure_storage_init()

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
    # Fetch mentions for response
    try:
        mentions_users = (
            db.query(User)
            .join(Mention, Mention.user_id == User.id)
            .filter(Mention.comment_id == new_comment.id)
            .all()
        )
    except Exception:
        mentions_users = []
    contact_mentions = _get_contact_mentions(db, new_comment.id)

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
        mentions=[UserResponse.from_orm(u) for u in mentions_users] if mentions_users else None,
        contact_mentions=[ContactResponse.from_orm(c) for c in contact_mentions] if contact_mentions else None,
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

