import json
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
from typing import Dict, List, Optional
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
from models import Violation, Citation, ActiveStorageAttachment, ActiveStorageBlob, User, Notification, ViolationCodePhoto
from sqlalchemy import or_
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
from urllib.parse import quote

router = APIRouter()

def _ensure_storage_init() -> None:
    """Ensure Azure storage clients are initialized so account metadata is populated."""
    storage.ensure_initialized()

def _parse_code_ids(raw_codes) -> List[int]:
    """Best-effort parsing for code IDs provided via multipart form or JSON body."""
    if raw_codes is None:
        return []
    # Already a list (from JSON body)
    if isinstance(raw_codes, list):
        parsed = []
        for val in raw_codes:
            try:
                parsed.append(int(val))
            except (TypeError, ValueError):
                continue
        return parsed
    if isinstance(raw_codes, str):
        txt = raw_codes.strip()
        if not txt:
            return []
        # Try JSON first
        try:
            data = json.loads(txt)
            if isinstance(data, list):
                parsed = []
                for val in data:
                    try:
                        parsed.append(int(val))
                    except (TypeError, ValueError):
                        continue
                return parsed
        except json.JSONDecodeError:
            pass
        # Fallback: comma-separated values
        parsed = []
        for part in txt.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                parsed.append(int(part))
            except ValueError:
                continue
        return parsed
    try:
        return [int(raw_codes)]
    except (TypeError, ValueError):
        return []

def _validate_codes_for_violation(violation: models.Violation, code_ids: List[int]) -> List[int]:
    """Ensure provided code IDs belong to the violation; return a deduped list or raise."""
    if not code_ids:
        return []
    allowed_ids = {c.id for c in getattr(violation, "codes", [])}
    cleaned: List[int] = []
    invalid: List[int] = []
    for cid in code_ids:
        if cid in allowed_ids:
            if cid not in cleaned:
                cleaned.append(cid)
        else:
            invalid.append(cid)
    if invalid:
        raise HTTPException(status_code=400, detail=f"Code(s) not attached to this violation: {', '.join(map(str, invalid))}")
    return cleaned

def _set_attachment_code_links(db: Session, violation_id: int, attachment_id: int, code_ids: List[int]) -> List[int]:
    """Replace code links for an attachment with the provided set."""
    db.query(ViolationCodePhoto).filter(
        ViolationCodePhoto.violation_id == violation_id,
        ViolationCodePhoto.attachment_id == attachment_id,
    ).delete(synchronize_session=False)
    for cid in code_ids:
        db.add(
            ViolationCodePhoto(
                violation_id=violation_id,
                code_id=cid,
                attachment_id=attachment_id,
                created_at=datetime.utcnow(),
            )
        )
    db.commit()
    return code_ids

def _load_violation_photo_blobs(db: Session, violation_id: int) -> List[Dict]:
    """Return violation attachments with their associated blobs and linked codes."""
    code_links = db.query(ViolationCodePhoto).filter(ViolationCodePhoto.violation_id == violation_id).all()
    codes_by_attachment: Dict[int, List[int]] = {}
    for link in code_links:
        codes_by_attachment.setdefault(link.attachment_id, []).append(link.code_id)

    attachment_rows = (
        db.query(ActiveStorageAttachment, ActiveStorageBlob)
        .join(ActiveStorageBlob, ActiveStorageBlob.id == ActiveStorageAttachment.blob_id)
        .filter(
            ActiveStorageAttachment.record_id == violation_id,
            ActiveStorageAttachment.record_type == 'Violation',
            ActiveStorageAttachment.name == 'photos',
        )
        .all()
    )
    results = []
    for attachment, blob in attachment_rows:
        results.append({
            "attachment": attachment,
            "blob": blob,
            "code_ids": codes_by_attachment.get(attachment.id, []),
        })
    return results

STATUS_STRING_TO_INT = {
    "current": 0,
    "resolved": 1,
    "pending trial": 2,
    "dismissed": 3,
}


def _merge_capture_metadata(exif_meta: dict, client_capture_raw: Optional[str]) -> dict:
    merged = dict(exif_meta or {})
    if client_capture_raw:
        try:
            client_meta = json.loads(client_capture_raw)
        except Exception:
            client_meta = {"raw": client_capture_raw}
        if client_meta:
            merged["client_capture"] = client_meta
    return merged


def _build_blob_url(key: str, sas_token: str) -> str:
    encoded_key = quote(key or "", safe="/")
    return f"https://{storage.account_name}.blob.core.windows.net/{storage.CONTAINER_NAME}/{encoded_key}?{sas_token}"

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
    unit_id: Optional[int] = Query(None),
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
    # Filter by unit if provided (supports frontend requests like /violations?unit_id=123)
    if unit_id is not None:
        query = query.filter(Violation.unit_id == unit_id)

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

# Replace codes attached to a violation (e.g., add a new code after creation)
@router.post("/violation/{violation_id}/codes", response_model=schemas.ViolationResponse)
def update_violation_codes(
    violation_id: int,
    codes: List[int] = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    violation = db.query(models.Violation).filter(models.Violation.id == violation_id).first()
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    if not isinstance(codes, list) or len(codes) == 0:
        raise HTTPException(status_code=400, detail="At least one code is required")

    code_rows = db.query(models.Code).filter(models.Code.id.in_(codes)).all()
    found_ids = {c.id for c in code_rows}
    missing = [str(c) for c in codes if c not in found_ids]
    if missing:
        raise HTTPException(status_code=400, detail=f"Code(s) not found: {', '.join(missing)}")

    violation.codes = code_rows
    db.commit()
    db.refresh(violation)
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
    # Return violations either directly on the address or attached to units belonging to the address
    from models import Unit

    violations_query = (
        db.query(Violation)
        .outerjoin(Unit, Violation.unit_id == Unit.id)
        .options(joinedload(Violation.codes), joinedload(Violation.unit), joinedload(Violation.address))
        .filter(or_(Violation.address_id == address_id, Unit.address_id == address_id))
        .order_by(Violation.created_at.desc())
    )

    violations = violations_query.all()

    # Build response list including codes, deadline_date and unit info
    response = []
    for violation in violations:
        violation_dict = violation.__dict__.copy()
        violation_dict['codes'] = violation.codes
        try:
            violation_dict['deadline_date'] = violation.deadline_date
        except Exception:
            violation_dict['deadline_date'] = None
        violation_dict['unit'] = getattr(violation, 'unit', None)
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
    capture_metadata: Optional[str] = Form(None),
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
            normalized_bytes, norm_filename, norm_ct, meta = normalize_image_for_web(content_bytes, file.filename, file.content_type)
            merged_meta = _merge_capture_metadata(meta, capture_metadata)
            blob_key = f"violation-comments/{new_comment.id}/{uuid.uuid4()}-{norm_filename}"
            blob_client = storage.blob_service_client.get_blob_client(container=storage.CONTAINER_NAME, blob=blob_key)
            blob_client.upload_blob(normalized_bytes, overwrite=True, content_type=norm_ct)

            blob_row = ActiveStorageBlob(
                key=blob_key,
                filename=norm_filename,
                content_type=norm_ct,
                meta_data=json.dumps(merged_meta) if merged_meta else None,
                service_name="azure",
                byte_size=len(normalized_bytes),
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
    violation.closed_at = datetime.utcnow()
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
    violation.closed_at = None
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

    attachment_rows = _load_violation_photo_blobs(db, violation_id)

    results = []
    for row in attachment_rows:
        attachment = row["attachment"]
        blob = row["blob"]
        if not blob or not attachment:
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
            url = _build_blob_url(blob.key, sas_token)
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
                    poster_url = _build_blob_url(poster_key, poster_sas)
                except Exception:
                    poster_url = None
            results.append({
                "id": attachment.id,
                "attachment_id": attachment.id,
                "blob_id": attachment.blob_id,
                "filename": blob.filename,
                "content_type": blob.content_type,
                "url": url,
                "poster_url": poster_url,
                "created_at": attachment.created_at.isoformat() if getattr(attachment, 'created_at', None) else None,
                "code_ids": row.get("code_ids") or [],
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
            url = _build_blob_url(blob.key, sas_token)
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
    code_ids: Optional[str] = Form(None),
    capture_metadata: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Upload attachments for a violation and create ActiveStorage records."""
    _ensure_storage_init()
    violation = db.query(models.Violation).filter(models.Violation.id == violation_id).first()
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")

    parsed_code_ids = _parse_code_ids(code_ids)
    validated_code_ids: List[int] = []
    if parsed_code_ids:
        validated_code_ids = _validate_codes_for_violation(violation, parsed_code_ids)

    uploaded = []
    for file in files:
        try:
            # Read and normalize image/video for web (HEIC->JPEG, MOV->MP4 handled downstream if needed)
            raw_bytes = await file.read()
            normalized_bytes, norm_filename, norm_ct, meta = normalize_image_for_web(raw_bytes, file.filename, file.content_type)
            merged_meta = _merge_capture_metadata(meta, capture_metadata)
            blob_key = f"violations/{violation_id}/{uuid.uuid4()}-{norm_filename}"
            blob_client = storage.blob_service_client.get_blob_client(container=storage.CONTAINER_NAME, blob=blob_key)
            blob_client.upload_blob(normalized_bytes, overwrite=True, content_type=norm_ct)

            blob_row = ActiveStorageBlob(
                key=blob_key,
                filename=norm_filename,
                content_type=norm_ct,
                meta_data=json.dumps(merged_meta) if merged_meta else None,
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
            if validated_code_ids:
                _set_attachment_code_links(db, violation_id, attachment_row.id, validated_code_ids)

            uploaded.append({
                "attachment_id": attachment_row.id,
                "filename": norm_filename,
                "content_type": norm_ct,
                "code_ids": validated_code_ids,
            })
        except Exception as e:
            logging.exception(f"Failed to upload attachment for Violation {violation_id}: {e}")
            continue

    return {"uploaded": uploaded}


# Update code associations for an existing violation attachment
@router.put("/violation/{violation_id}/photos/{attachment_id}/codes")
def update_violation_photo_codes(
    violation_id: int,
    attachment_id: int,
    payload: schemas.AttachmentCodeUpdate,
    db: Session = Depends(get_db),
):
    violation = db.query(models.Violation).options(joinedload(models.Violation.codes)).filter(models.Violation.id == violation_id).first()
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")

    attachment = (
        db.query(ActiveStorageAttachment)
        .filter(
            ActiveStorageAttachment.id == attachment_id,
            ActiveStorageAttachment.record_type == "Violation",
            ActiveStorageAttachment.record_id == violation_id,
        )
        .first()
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found for this violation")

    validated_code_ids = _validate_codes_for_violation(violation, payload.code_ids or [])
    _set_attachment_code_links(db, violation_id, attachment_id, validated_code_ids)

    return {"attachment_id": attachment_id, "code_ids": validated_code_ids}


