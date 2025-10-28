from datetime import date, datetime, timedelta
from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    Body,
    UploadFile,
    File,
    Form,
    Response,
    Query,
)
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
from models import Violation, Citation, ActiveStorageAttachment, ActiveStorageBlob, User, Notification
from email_service import send_notification_email
import schemas
from database import get_db
from sqlalchemy import desc
import models
import storage
from image_utils import normalize_image_for_web
from media_service import ensure_blob_browser_safe
import uuid
import logging

router = APIRouter()

def _ensure_storage_init() -> None:
    """Ensure Azure storage clients are initialized so account metadata is populated."""
    storage.ensure_initialized()

STATUS_STRING_TO_INT = {
    "current": 0,
    "resolved": 1,
    "pending trial": 2,
    "dismissed": 3,
}

# Extend deadline for a violation
@router.patch("/violation/{violation_id}/deadline", response_model=schemas.ViolationResponse)
def extend_violation_deadline(violation_id: int, extend: int = Body(..., embed=True), db: Session = Depends(get_db)):
    violation = db.query(models.Violation).filter(models.Violation.id == violation_id).first()
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    violation.extend = extend
    db.commit()
    db.refresh(violation)
    return violation

# Get all violations
@router.get("/violations/", response_model=List[schemas.ViolationResponse])
def get_violations(
    response: Response,
    skip: int = 0,
    limit: Optional[int] = Query(None, ge=0),
    status: Optional[str] = Query(None),
    assigned_user_id: Optional[int] = Query(None),
    user_email: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Violation)

    if status:
        status_key = status.strip().lower()
        if status_key not in STATUS_STRING_TO_INT:
            raise HTTPException(status_code=400, detail="Invalid status filter")
        query = query.filter(Violation.status == STATUS_STRING_TO_INT[status_key])

    if assigned_user_id is not None:
        query = query.filter(Violation.user_id == assigned_user_id)
    elif user_email:
        query = query.join(Violation.user).filter(User.email == user_email)

    total = query.count()

    # Cap the limit to avoid unbounded responses if a very large number is supplied.
    if limit is not None:
        if limit == 0:
            limit = None
        else:
            limit = min(limit, 200)

    violations_query = query.options(
        joinedload(Violation.address),
        joinedload(Violation.codes),
        joinedload(Violation.user),  # Eagerly load User relationship
    ).order_by(desc(Violation.created_at))

    if skip:
        violations_query = violations_query.offset(skip)
    if limit is not None:
        violations_query = violations_query.limit(limit)

    violations = violations_query.all()

    response.headers["X-Total-Count"] = str(total)

    response = []
    for violation in violations:
        violation_dict = violation.__dict__.copy()
        violation_dict['combadd'] = violation.address.combadd if violation.address else None
        violation_dict['deadline_date'] = violation.deadline_date
        violation_dict['codes'] = violation.codes
        violation_dict['user'] = schemas.UserResponse.from_orm(violation.user) if getattr(violation, 'user', None) else None
        response.append(violation_dict)
    return response

# Create a new violation
@router.post("/violations/", response_model=schemas.ViolationResponse)
def create_violation(violation: schemas.ViolationCreate, db: Session = Depends(get_db)):
    violation_data = violation.dict(exclude={"codes"})
    # Ensure violation_type is set, default to "doorhanger" if not provided
    if not violation_data.get("violation_type"):
        violation_data["violation_type"] = "doorhanger"
    # Always set status to 0 (current) if not provided
    if not violation_data.get("status"):
        violation_data["status"] = 0
    new_violation = Violation(**violation_data)
    db.add(new_violation)
    db.commit()
    # Associate codes if provided
    if violation.codes:
        codes = db.query(models.Code).filter(models.Code.id.in_(violation.codes)).all()
        new_violation.codes = codes
        db.commit()
    db.refresh(new_violation)
    return new_violation

# Reassign a violation to a different user
@router.patch("/violation/{violation_id}/assignee", response_model=schemas.ViolationResponse)
def update_violation_assignee(
    violation_id: int,
    user_id: int = Form(...),
    db: Session = Depends(get_db),
):
    violation = db.query(models.Violation).filter(models.Violation.id == violation_id).first()
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")

    assignee = db.query(User).filter(User.id == user_id).first()
    if not assignee:
        raise HTTPException(status_code=404, detail="User not found")

    violation.user_id = user_id
    db.commit()

    return get_violation(violation_id, db)
# Get a specific violation by ID
@router.get("/violation/{violation_id}", response_model=schemas.ViolationResponse)
def get_violation(violation_id: int, db: Session = Depends(get_db)):
    violation = (
        db.query(Violation)
        .filter(Violation.id == violation_id)
        .options(
            joinedload(Violation.address),
            joinedload(Violation.codes),
            joinedload(Violation.user)  # Eagerly load the user relationship
        )
        .first()
    )
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    # Add combadd and codes to the response
    violation_dict = violation.__dict__.copy()
    violation_dict['combadd'] = violation.address.combadd if violation.address else None
    violation_dict['deadline_date'] = violation.deadline_date
    violation_dict['codes'] = violation.codes
    violation_dict['user'] = schemas.UserResponse.from_orm(violation.user) if getattr(violation, 'user', None) else None
    violation_dict['violation_comments'] = [
        {
            'id': vc.id,
            'content': vc.content,
            'user_id': vc.user_id,
            'violation_id': vc.violation_id,
            'created_at': vc.created_at,
            'updated_at': vc.updated_at,
            'user': schemas.UserResponse.from_orm(vc.user) if getattr(vc, 'user', None) else None
        }
        for vc in violation.violation_comments
    ] if hasattr(violation, 'violation_comments') else []
    return violation_dict

    print("violation.user:", violation.user)
    print("violation_dict['user']:", violation_dict.get('user'))


# Get all violations for a specific Address
@router.get("/violations/address/{address_id}", response_model=List[schemas.ViolationResponse])
def get_violations_by_address(address_id: int, db: Session = Depends(get_db)):
    violations = db.query(Violation).options(joinedload(Violation.codes)).filter(Violation.address_id == address_id).all()
    # Add codes and deadline_date to the response
    response = []
    for violation in violations:
        violation_dict = violation.__dict__.copy()
        violation_dict['codes'] = violation.codes
        violation_dict['deadline_date'] = violation.deadline_date  # Ensure this computed property is included
        response.append(violation_dict)
    return response

# Show all citations for a specific Violation
@router.get("/violation/{violation_id}/citations", response_model=List[schemas.CitationResponse])
def get_citations_by_violation(violation_id: int, db: Session = Depends(get_db)):
    citations = (
        db.query(Citation)
        .options(
            joinedload(Citation.violation).joinedload(Violation.address),
            joinedload(Citation.code),
            joinedload(Citation.user)  # Eagerly load the User relationship
        )
        .filter(Citation.violation_id == violation_id)
        .all()
    )

    # Add combadd, code_name, and user to the response
    response = []
    for citation in citations:
        citation_dict = citation.__dict__.copy()
        citation_dict['combadd'] = citation.violation.address.combadd if citation.violation and citation.violation.address else None
        citation_dict['code_name'] = citation.code.name if citation.code else None
        citation_dict['user'] = schemas.UserResponse.from_orm(citation.user) if getattr(citation, 'user', None) else None
        response.append(citation_dict)
    return response

# Delete a violation by ID
@router.delete("/violations/{violation_id}", status_code=204)
def delete_violation(violation_id: int, db: Session = Depends(get_db)):
    vio = db.query(models.Violation).filter(models.Violation.id == violation_id).first()
    if not vio:
        raise HTTPException(status_code=404, detail="Violation not found")
    try:
        db.delete(vio)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Unable to delete violation due to related records")

# Add a comment to a violation
@router.post("/violation/{violation_id}/comments", response_model=schemas.ViolationCommentResponse)
def add_violation_comment(violation_id: int, comment: schemas.ViolationCommentCreate, db: Session = Depends(get_db)):
    # Ensure violation exists
    violation = db.query(models.Violation).filter(models.Violation.id == violation_id).first()
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    # Create new comment
    new_comment = models.ViolationComment(
        content=comment.content,
        user_id=comment.user_id,
        violation_id=violation_id
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    # Notify the assigned user on the violation (if different from author)
    try:
        if getattr(violation, 'user_id', None) and int(violation.user_id) != int(new_comment.user_id):
            notif = Notification(
                title="New comment on violation",
                body=(new_comment.content or "").strip(),
                inspection_id=None,
                comment_id=new_comment.id,  # reused across comment types for origin resolution
                user_id=int(violation.user_id),
                read=False,
            )
            db.add(notif)
            db.commit()
            # Best-effort email
            try:
                target_user = db.query(models.User).filter(models.User.id == int(violation.user_id)).first()
                if target_user and getattr(target_user, 'email', None):
                    send_notification_email(
                        subject="New violation comment",
                        body=new_comment.content or "",
                        to_email=target_user.email,
                        inspection_id=None,
                    )
            except Exception:
                pass
    except Exception:
        # Do not fail the request due to notification issues
        db.rollback()
    # Optionally, fetch user info for response
    user = db.query(models.User).filter(models.User.id == new_comment.user_id).first()
    user_response = schemas.UserResponse.from_orm(user) if user else None
    return schemas.ViolationCommentResponse(
        id=new_comment.id,
        content=new_comment.content,
        user_id=new_comment.user_id,
        violation_id=new_comment.violation_id,
        created_at=new_comment.created_at,
        updated_at=new_comment.updated_at,
        user=user_response
    )

# Create a violation comment with optional file attachments (multipart form)
@router.post("/violation/{violation_id}/comments/upload", response_model=schemas.ViolationCommentResponse)
async def add_violation_comment_with_attachments(
    violation_id: int,
    content: str = Form(...),
    user_id: int = Form(...),
    files: List[UploadFile] = File([]),
    db: Session = Depends(get_db),
):
    # Ensure violation exists
    violation = db.query(models.Violation).filter(models.Violation.id == violation_id).first()
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")

    # Create comment first
    new_comment = models.ViolationComment(content=content, user_id=user_id, violation_id=violation_id)
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    # Notify the assigned user on the violation (if different from author)
    try:
        if getattr(violation, 'user_id', None) and int(violation.user_id) != int(new_comment.user_id):
            notif = Notification(
                title="New comment on violation",
                body=(new_comment.content or "").strip(),
                inspection_id=None,
                comment_id=new_comment.id,
                user_id=int(violation.user_id),
                read=False,
            )
            db.add(notif)
            db.commit()
            # Best-effort email
            try:
                target_user = db.query(models.User).filter(models.User.id == int(violation.user_id)).first()
                if target_user and getattr(target_user, 'email', None):
                    send_notification_email(
                        subject="New violation comment",
                        body=new_comment.content or "",
                        to_email=target_user.email,
                        inspection_id=None,
                    )
            except Exception:
                pass
    except Exception:
        # Do not fail the request due to notification issues
        db.rollback()

    # Upload attachments (if any)
    for file in files:
        try:
            content_bytes = await file.read()
            blob_key = f"violation-comments/{new_comment.id}/{uuid.uuid4()}-{file.filename}"
            blob_client = storage.blob_service_client.get_blob_client(container=storage.CONTAINER_NAME, blob=blob_key)
            blob_client.upload_blob(content_bytes, overwrite=True, content_type=file.content_type)

            blob_row = ActiveStorageBlob(
                key=blob_key,
                filename=file.filename,
                content_type=file.content_type,
                meta_data=None,
                service_name="azure",
                byte_size=len(content_bytes),
                checksum=None,
                created_at=datetime.utcnow(),
            )
            db.add(blob_row)
            db.commit()
            db.refresh(blob_row)

            attachment_row = ActiveStorageAttachment(
                name="attachments",
                record_type="ViolationComment",
                record_id=new_comment.id,
                blob_id=blob_row.id,
                created_at=datetime.utcnow(),
            )
            db.add(attachment_row)
            db.commit()
        except Exception as e:
            logging.exception(f"Failed to upload attachment for ViolationComment {new_comment.id}: {e}")
            continue

    # Build response with optional user
    user = db.query(models.User).filter(models.User.id == new_comment.user_id).first()
    user_response = schemas.UserResponse.from_orm(user) if user else None
    return schemas.ViolationCommentResponse(
        id=new_comment.id,
        content=new_comment.content,
        user_id=new_comment.user_id,
        violation_id=new_comment.violation_id,
        created_at=new_comment.created_at,
        updated_at=new_comment.updated_at,
        user=user_response,
    )

# Abate (close) a violation
@router.post("/violation/{violation_id}/abate", response_model=schemas.ViolationResponse)
def abate_violation(violation_id: int, db: Session = Depends(get_db)):
    violation = db.query(models.Violation).options(joinedload(models.Violation.user)).filter(models.Violation.id == violation_id).first()
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    violation.status = 1  # 1 = Resolved/Closed
    db.commit()
    db.refresh(violation)
    violation_dict = violation.__dict__.copy()
    violation_dict['combadd'] = violation.address.combadd if violation.address else None
    violation_dict['deadline_date'] = violation.deadline_date
    violation_dict['codes'] = violation.codes
    violation_dict['user'] = schemas.UserResponse.from_orm(violation.user) if getattr(violation, 'user', None) else None
    violation_dict['violation_comments'] = [
        {
            'id': vc.id,
            'content': vc.content,
            'user_id': vc.user_id,
            'violation_id': vc.violation_id,
            'created_at': vc.created_at,
            'updated_at': vc.updated_at,
            'user': schemas.UserResponse.from_orm(vc.user) if getattr(vc, 'user', None) else None
        }
        for vc in violation.violation_comments
    ] if hasattr(violation, 'violation_comments') else []
    return violation_dict

# Reopen a violation (set status back to current)
@router.post("/violation/{violation_id}/reopen", response_model=schemas.ViolationResponse)
def reopen_violation(violation_id: int, db: Session = Depends(get_db)):
    violation = db.query(models.Violation).options(joinedload(models.Violation.user)).filter(models.Violation.id == violation_id).first()
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    violation.status = 0  # 0 = Current/Open
    db.commit()
    db.refresh(violation)
    violation_dict = violation.__dict__.copy()
    violation_dict['combadd'] = violation.address.combadd if violation.address else None
    violation_dict['deadline_date'] = violation.deadline_date
    violation_dict['codes'] = violation.codes
    violation_dict['user'] = schemas.UserResponse.from_orm(violation.user) if getattr(violation, 'user', None) else None
    violation_dict['violation_comments'] = [
        {
            'id': vc.id,
            'content': vc.content,
            'user_id': vc.user_id,
            'violation_id': vc.violation_id,
            'created_at': vc.created_at,
            'updated_at': vc.updated_at,
            'user': schemas.UserResponse.from_orm(vc.user) if getattr(vc, 'user', None) else None
        }
        for vc in violation.violation_comments
    ] if hasattr(violation, 'violation_comments') else []
    return violation_dict

# -------------------------
# Attachments (Photos) for Violations
# -------------------------

@router.get("/violation/{violation_id}/photos")
def get_violation_photos(violation_id: int, download: bool = False, db: Session = Depends(get_db)):
    """Return signed URLs for attachments on a Violation, similar to comment photos."""
    _ensure_storage_init()
    violation = db.query(models.Violation).filter(models.Violation.id == violation_id).first()
    if not violation:
        # Keep behavior lenient (like comments): return empty list if missing
        return []

    attachments = db.query(ActiveStorageAttachment).filter(
        ActiveStorageAttachment.record_id == violation_id,
        ActiveStorageAttachment.record_type == 'Violation',
        ActiveStorageAttachment.name == 'photos',
    ).all()

    results = []
    for attachment in attachments:
        blob = db.query(ActiveStorageBlob).filter(ActiveStorageBlob.id == attachment.blob_id).first()
        if not blob:
            continue
        # Ensure browser-safe; convert on-demand if needed (e.g., HEIC to JPEG, MOV to MP4)
        try:
            blob = ensure_blob_browser_safe(db, blob)
        except Exception as e:
            logging.exception(f"On-demand conversion failed for blob {getattr(blob, 'key', '?')}: {e}")
            # Continue with the original blob if conversion fails
        try:
            sas_token = generate_blob_sas(
                account_name=storage.account_name,
                container_name=storage.CONTAINER_NAME,
                blob_name=blob.key,
                account_key=storage.account_key,
                permission=BlobSasPermissions(read=True),
                start=datetime.utcnow() - timedelta(minutes=5),
                expiry=datetime.utcnow() + timedelta(hours=1),
                content_disposition=(f'attachment; filename="{blob.filename}"' if download else None),
            )
            url = f"https://{storage.account_name}.blob.core.windows.net/{storage.CONTAINER_NAME}/{blob.key}?{sas_token}"
            poster_url = None
            if (blob.content_type or "").startswith("video/") and blob.key.lower().endswith('.mp4'):
                base = blob.key[:-4]
                poster_key = f"{base}-poster.jpg"
                try:
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
            results.append({
                "filename": blob.filename,
                "content_type": blob.content_type,
                "url": url,
                "poster_url": poster_url,
                "created_at": attachment.created_at.isoformat() if getattr(attachment, 'created_at', None) else None,
            })
        except Exception as e:
            logging.exception(f"Failed generating SAS for blob {blob.key}: {e}")
            continue

    return results

# Fetch attachments for a specific violation comment
@router.get("/violation/comment/{comment_id}/attachments")
def get_violation_comment_attachments(comment_id: int, download: bool = False, db: Session = Depends(get_db)):
    _ensure_storage_init()
    vc = db.query(models.ViolationComment).filter(models.ViolationComment.id == comment_id).first()
    if not vc:
        raise HTTPException(status_code=404, detail="ViolationComment not found")

    attachments = db.query(ActiveStorageAttachment).filter(
        ActiveStorageAttachment.record_id == comment_id,
        ActiveStorageAttachment.record_type == "ViolationComment",
        ActiveStorageAttachment.name == "attachments",
    ).all()

    results = []
    for attachment in attachments:
        blob = db.query(ActiveStorageBlob).filter(ActiveStorageBlob.id == attachment.blob_id).first()
        if not blob:
            continue
        try:
            sas_token = generate_blob_sas(
                account_name=storage.account_name,
                container_name=storage.CONTAINER_NAME,
                blob_name=blob.key,
                account_key=storage.account_key,
                permission=BlobSasPermissions(read=True),
                start=datetime.utcnow() - timedelta(minutes=5),
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


@router.post("/violation/{violation_id}/photos")
async def upload_violation_photos(
    violation_id: int,
    files: List[UploadFile] = File([]),
    db: Session = Depends(get_db),
):
    """Upload attachments for a violation and create ActiveStorage records."""
    _ensure_storage_init()
    violation = db.query(models.Violation).filter(models.Violation.id == violation_id).first()
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")

    uploaded = []
    for file in files:
        try:
            # Read and normalize image/video for web (HEIC->JPEG, MOV->MP4 handled downstream if needed)
            raw_bytes = await file.read()
            normalized_bytes, norm_filename, norm_ct = normalize_image_for_web(raw_bytes, file.filename, file.content_type)
            blob_key = f"violations/{violation_id}/{uuid.uuid4()}-{norm_filename}"
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
                name="photos",
                record_type="Violation",
                record_id=violation_id,
                blob_id=blob_row.id,
                created_at=datetime.utcnow(),
            )
            db.add(attachment_row)
            db.commit()

            uploaded.append({
                "filename": norm_filename,
                "content_type": norm_ct,
            })
        except Exception as e:
            logging.exception(f"Failed to upload attachment for Violation {violation_id}: {e}")
            continue

    return {"uploaded": uploaded}



