from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from models import Inspection, Contact, Address, Area, Room, Prompt, Observation, Photo, ActiveStorageAttachment, ActiveStorageBlob, License, Permit, Violation, User, Notification, InspectionComment
from schemas import InspectionResponse, ContactResponse, AddressResponse, AreaResponse, AreaCreate, RoomResponse, RoomCreate, PromptCreate, PromptResponse, ObservationCreate, ObservationResponse, ObservationUpdate
from schemas import InspectionResponse, ContactResponse, AddressResponse, AreaResponse, AreaCreate, RoomResponse, RoomCreate, PromptCreate, PromptResponse, ObservationCreate, ObservationResponse, PotentialObservationResponse
# add import for inspection comment schemas
from schemas import InspectionCommentCreate, InspectionCommentResponse
from database import get_db
# reuse mention helpers from the generic comments routes
from routes.comments import _handle_user_mentions, _store_contact_mentions, _collect_contact_ids, _get_contact_mentions
from schemas import UserResponse
from models import Code
import storage
from image_utils import normalize_image_for_web
from datetime import datetime, timedelta, date
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
import uuid
from media_service import ensure_blob_browser_safe
from email_service import send_notification_email
from .auth import get_current_user, get_current_user_optional

router = APIRouter()

# Internal helper to create a notification when assigning/reassigning
def _create_assignment_notification(
    db: Session,
    inspection: Inspection,
    inspector_id: Optional[int],
    actor_user_id: Optional[int] = None,
):
    if not inspector_id:
        return
    try:
        inspector_int = int(inspector_id)
    except (TypeError, ValueError):
        return
    if actor_user_id is not None:
        try:
            actor_int = int(actor_user_id)
        except (TypeError, ValueError):
            actor_int = None
        if actor_int == inspector_int:
            return
    try:
        title = "Inspection assigned"
        body = f"You have been assigned to inspection #{inspection.id}."
        notif = Notification(
            title=title,
            body=body,
            inspection_id=inspection.id,
            user_id=inspector_int,
            read=False,
        )
        db.add(notif)
        db.commit()
        # Email: prefer actual recipient; allow override via env TEST_EMAIL_USER_ID
        try:
            import os
            override_id = os.getenv("TEST_EMAIL_USER_ID")
            target_user_id = int(override_id) if override_id else inspector_int
            target_user = db.query(User).filter(User.id == target_user_id).first()
            if target_user and target_user.email:
                send_notification_email(subject=title, body=body, to_email=target_user.email, inspection_id=inspection.id)
        except Exception:
            pass
    except Exception:
        db.rollback()
        # Silent failure; we don't want assignment to fail due to notification
        pass

def _notify_admins_unassigned_complaint(db: Session, inspection: Inspection):
    """
    Alert all admins whenever a complaint is created without an inspector assignment.
    """
    source_label = (inspection.source or "").lower()
    if source_label != "complaint":
        return
    if inspection.inspector_id:
        return

    admins = db.query(User).filter(User.role == 3).all()
    recipients = []
    seen_ids = set()
    for admin in admins:
        try:
            admin_id = int(admin.id)
        except (TypeError, ValueError):
            continue
        if admin_id in seen_ids:
            continue
        seen_ids.add(admin_id)
        recipients.append((admin_id, admin))

    if not recipients:
        return

    address_label = None
    if inspection.address_id:
        address = db.query(Address).filter(Address.id == inspection.address_id).first()
        if address and getattr(address, "combadd", None):
            address_label = address.combadd

    location_text = ""
    if address_label:
        location_text = f" at {address_label}"
    elif inspection.address_id:
        location_text = f" at address #{inspection.address_id}"

    title = "New complaint needs assignment"
    body = f"Complaint #{inspection.id}{location_text} does not have an inspector assigned. Please review and assign an inspector."

    try:
        for admin_id, _admin in recipients:
            notif = Notification(
                title=title,
                body=body,
                inspection_id=inspection.id,
                user_id=admin_id,
                read=False,
            )
            db.add(notif)
        db.commit()
    except Exception:
        db.rollback()
        return

    for _admin_id, admin in recipients:
        email = getattr(admin, "email", None)
        if not email:
            continue
        try:
            send_notification_email(subject=title, body=body, to_email=email, inspection_id=inspection.id)
        except Exception:
            # Ignore email failures; the in-app notification already exists
            continue

# Get all inspections
@router.get("/inspections/", response_model=List[InspectionResponse])
def get_inspections(skip: int = 0, db: Session = Depends(get_db)):
    """
    Get all inspections (excluding complaints).

    Args:
        skip (int): Pagination offset.
        db (Session): The database session.

    Returns:
        list[InspectionResponse]: A list of inspections.
    """
    inspections = (
        db.query(Inspection)
        .options(joinedload(Inspection.address))
        .filter(Inspection.source != 'Complaint')
        .order_by(Inspection.created_at.desc())
        .offset(skip)
        .all()
    )
    return inspections

# Get all complaints
@router.get("/complaints/", response_model=List[InspectionResponse])
def get_complaints(skip: int = 0, db: Session = Depends(get_db)):
    """
    Get all complaints (inspections with source='Complaint').

    Args:
        skip (int): Pagination offset.
        db (Session): The database session.

    Returns:
        list[InspectionResponse]: A list of complaints.
    """
    complaints = (
        db.query(Inspection)
        .options(joinedload(Inspection.address))
        .filter(Inspection.source == 'Complaint')
        .order_by(Inspection.created_at.desc())
        .offset(skip)
        .all()
    )
    return complaints

# Delete an inspection by ID
@router.delete("/inspections/{inspection_id}", status_code=204)
def delete_inspection(inspection_id: int, db: Session = Depends(get_db)):
    """
    Delete an inspection.

    Args:
        inspection_id (int): The ID of the inspection.
        db (Session): The database session.

    Raises:
        HTTPException: If inspection not found or deletion fails.
    """
    insp = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection not found")
    try:
        # Clean up dependent records to avoid FK constraint failures
        from models import License as LicenseModel, Permit as PermitModel, Notification as NotificationModel
        from models import InspectionComment as InspectionCommentModel, InspectionCode as InspectionCodeModel, Area as AreaModel, Observation as ObservationModel, Photo as PhotoModel
        from models import Violation as ViolationModel, Citation as CitationModel, ViolationComment as ViolationCommentModel, ViolationCode as ViolationCodeModel

        # Delete licenses and permits linked to this inspection
        db.query(LicenseModel).filter(LicenseModel.inspection_id == inspection_id).delete(synchronize_session=False)
        db.query(PermitModel).filter(PermitModel.inspection_id == inspection_id).delete(synchronize_session=False)

        # Delete notifications linked to this inspection
        db.query(NotificationModel).filter(NotificationModel.inspection_id == inspection_id).delete(synchronize_session=False)

        # Delete inspection comments and codes
        db.query(InspectionCommentModel).filter(InspectionCommentModel.inspection_id == inspection_id).delete(synchronize_session=False)
        db.query(InspectionCodeModel).filter(InspectionCodeModel.inspection_id == inspection_id).delete(synchronize_session=False)

        # Areas: compute observation ids first, delete photos -> observations -> areas
        area_ids = [row.id for row in db.query(AreaModel.id).filter(AreaModel.inspection_id == inspection_id).all()]
        if area_ids:
            obs_ids = [row.id for row in db.query(ObservationModel.id).filter(ObservationModel.area_id.in_(area_ids)).all()]
            if obs_ids:
                db.query(PhotoModel).filter(PhotoModel.observation_id.in_(obs_ids)).delete(synchronize_session=False)
                db.query(ObservationModel).filter(ObservationModel.id.in_(obs_ids)).delete(synchronize_session=False)
            db.query(AreaModel).filter(AreaModel.id.in_(area_ids)).delete(synchronize_session=False)

        # Violations linked to this inspection and their dependents
        vio_ids = [row.id for row in db.query(ViolationModel.id).filter(ViolationModel.inspection_id == inspection_id).all()]
        if vio_ids:
            # Delete citations
            db.query(CitationModel).filter(CitationModel.violation_id.in_(vio_ids)).delete(synchronize_session=False)
            # Delete violation comments
            db.query(ViolationCommentModel).filter(ViolationCommentModel.violation_id.in_(vio_ids)).delete(synchronize_session=False)
            # Delete violation<->code join rows
            db.query(ViolationCodeModel).filter(ViolationCodeModel.violation_id.in_(vio_ids)).delete(synchronize_session=False)
            # Finally delete violations
            db.query(ViolationModel).filter(ViolationModel.id.in_(vio_ids)).delete(synchronize_session=False)

        db.delete(insp)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Unable to delete inspection due to related records")

# Delete a complaint by ID (complaint is an Inspection with source 'Complaint')
@router.delete("/complaints/{inspection_id}", status_code=204)
def delete_complaint(inspection_id: int, db: Session = Depends(get_db)):
    """
    Delete a complaint.

    Args:
        inspection_id (int): The ID of the complaint.
        db (Session): The database session.

    Raises:
        HTTPException: If complaint not found or deletion fails.
    """
    insp = db.query(Inspection).filter(Inspection.id == inspection_id, Inspection.source == 'Complaint').first()
    if not insp:
        raise HTTPException(status_code=404, detail="Complaint not found")
    try:
        # Clean up dependent records (same as inspections)
        from models import License as LicenseModel, Permit as PermitModel, Notification as NotificationModel
        from models import InspectionComment as InspectionCommentModel, InspectionCode as InspectionCodeModel, Area as AreaModel, Observation as ObservationModel, Photo as PhotoModel
        from models import Violation as ViolationModel, Citation as CitationModel, ViolationComment as ViolationCommentModel, ViolationCode as ViolationCodeModel

        db.query(LicenseModel).filter(LicenseModel.inspection_id == inspection_id).delete(synchronize_session=False)
        db.query(PermitModel).filter(PermitModel.inspection_id == inspection_id).delete(synchronize_session=False)
        db.query(NotificationModel).filter(NotificationModel.inspection_id == inspection_id).delete(synchronize_session=False)
        db.query(InspectionCommentModel).filter(InspectionCommentModel.inspection_id == inspection_id).delete(synchronize_session=False)
        db.query(InspectionCodeModel).filter(InspectionCodeModel.inspection_id == inspection_id).delete(synchronize_session=False)
        area_ids = [row.id for row in db.query(AreaModel.id).filter(AreaModel.inspection_id == inspection_id).all()]
        if area_ids:
            obs_ids = [row.id for row in db.query(ObservationModel.id).filter(ObservationModel.area_id.in_(area_ids)).all()]
            if obs_ids:
                db.query(PhotoModel).filter(PhotoModel.observation_id.in_(obs_ids)).delete(synchronize_session=False)
                db.query(ObservationModel).filter(ObservationModel.id.in_(obs_ids)).delete(synchronize_session=False)
            db.query(AreaModel).filter(AreaModel.id.in_(area_ids)).delete(synchronize_session=False)

        vio_ids = [row.id for row in db.query(ViolationModel.id).filter(ViolationModel.inspection_id == inspection_id).all()]
        if vio_ids:
            db.query(CitationModel).filter(CitationModel.violation_id.in_(vio_ids)).delete(synchronize_session=False)
            db.query(ViolationCommentModel).filter(ViolationCommentModel.violation_id.in_(vio_ids)).delete(synchronize_session=False)
            db.query(ViolationCodeModel).filter(ViolationCodeModel.violation_id.in_(vio_ids)).delete(synchronize_session=False)
            db.query(ViolationModel).filter(ViolationModel.id.in_(vio_ids)).delete(synchronize_session=False)

        db.delete(insp)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Unable to delete complaint due to related records")

# Create a new inspection
@router.post("/inspections/", response_model=InspectionResponse)
async def create_inspection(
    address_id: Optional[int] = Form(None),
    unit_id: Optional[int] = Form(None),
    source: str = Form(...),
    description: str = Form(""),
    contact_id: Optional[int] = Form(None),
    attachments: List[UploadFile] = File([]),
    paid: bool = Form(False),
    inspector_id: Optional[int] = Form(None),
    business_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Create a new inspection or complaint.

    Args:
        address_id (int, optional): Address ID.
        unit_id (int, optional): Unit ID.
        source (str): Source of inspection.
        description (str): Description.
        contact_id (int, optional): Contact ID.
        attachments (list[UploadFile]): Files to upload.
        paid (bool): Paid status.
        inspector_id (int, optional): Assigned inspector ID.
        business_id (int, optional): Business ID.
        db (Session): The database session.
        current_user (User, optional): The user creating the inspection.

    Returns:
        InspectionResponse: The created inspection.
    """
    new_inspection = Inspection(
        address_id=address_id,
        unit_id=unit_id,
        source=source,
        description=description,
        contact_id=contact_id,
        paid=paid,
        inspector_id=inspector_id,
        business_id=business_id,
    )
    db.add(new_inspection)
    db.commit()
    db.refresh(new_inspection)

    for attachment in attachments:
        try:
            raw = await attachment.read()
            normalized_bytes, norm_filename, norm_ct = normalize_image_for_web(raw, attachment.filename, attachment.content_type)
            blob_key = f"inspections/{new_inspection.id}/{uuid.uuid4()}-{norm_filename}"
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
                record_type="Inspection",
                record_id=new_inspection.id,
                blob_id=blob_row.id,
                created_at=datetime.utcnow(),
            )
            db.add(attachment_row)
            db.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload file {attachment.filename}: {str(e)}")

    db.commit()

    # Notifications
    actor_id = getattr(current_user, "id", None)
    _create_assignment_notification(db, new_inspection, inspector_id, actor_user_id=actor_id)
    _notify_admins_unassigned_complaint(db, new_inspection)

    return new_inspection

# Get a specific inspection by ID
@router.get("/inspections/{inspection_id}", response_model=InspectionResponse)
def get_inspection(inspection_id: int, db: Session = Depends(get_db)):
    """
    Get an inspection by ID.

    Args:
        inspection_id (int): The ID of the inspection.
        db (Session): The database session.

    Returns:
        InspectionResponse: The inspection details.

    Raises:
        HTTPException: If inspection is not found.
    """
    inspection = (
      db.query(Inspection)
      .options(
        joinedload(Inspection.address),  # Eagerly load address relationship
        joinedload(Inspection.contact)  # Eagerly load contact relationship
      )
      .filter(Inspection.id == inspection_id)
      .first()
      )

    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    # Provide a compatibility fallback so clients can read a description-like field
    try:
        existing_comment = getattr(inspection, 'comment', None)
        desc = getattr(inspection, 'description', None)
        if not existing_comment:
            fallback = None
            for key in ('description', 'result', 'notes_area_1', 'notes_area_2', 'notes_area_3', 'thoughts'):
                val = getattr(inspection, key, None)
                if isinstance(val, str) and val.strip():
                    fallback = val.strip()
                    break
            setattr(inspection, 'comment', fallback)
    except Exception:
        # non-fatal; continue returning the inspection
        pass
    return inspection

# Update status for an inspection (e.g., complaint)
@router.patch("/inspections/{inspection_id}/status", response_model=InspectionResponse)
def update_inspection_status(inspection_id: int, status: str = Form(...), db: Session = Depends(get_db)):
    """
    Update inspection status.

    Args:
        inspection_id (int): The ID of the inspection.
        status (str): The new status.
        db (Session): The database session.

    Returns:
        InspectionResponse: The updated inspection.

    Raises:
        HTTPException: If inspection is not found.
    """
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    inspection.status = status
    db.commit()

    # If a license-related inspection is marked completed, create a License record once
    status_lower = (status or "").lower()
    is_completed = status_lower in ("completed", "satisfactory")
    src = (inspection.source or "").lower()
    status_message = None

    # Unified auto-create logic for license / permit with explicit messaging
    try:
        if is_completed:
            license_sources = {
                "business license": 1,
                "single family license": 2,
                "multifamily license": 3,
            }
            permit_keywords = ["permit", "building/dumpster/pod"]

            created_any = False

            # Determine if this inspection should create a license
            is_license_source = src in license_sources and not any(k in src for k in permit_keywords)
            # Determine if this inspection should create a permit
            is_permit_source = any(k in src for k in permit_keywords)

            # Attempt license creation first (business rule priority)
            if is_license_source:
                open_violation_exists = (
                    db.query(Violation.id)
                    .filter(
                        Violation.address_id == inspection.address_id,
                        Violation.status == 0
                    )
                    .first()
                    is not None
                )
                if open_violation_exists:
                    status_message = "License not created: open violations exist at this address."
                else:
                    existing_license = db.query(License).filter(License.inspection_id == inspection.id).first()
                    if existing_license:
                        status_message = f"License already exists (#{existing_license.id})."
                    else:
                        today = date.today()
                        fy_end_year = today.year if today.month < 7 else today.year + 1
                        fiscal_year = f"{fy_end_year - 1}-{fy_end_year}"
                        new_license = License(
                            inspection_id=inspection.id,
                            sent=False,
                            revoked=False,
                            fiscal_year=fiscal_year,
                            expiration_date=date(fy_end_year, 6, 30),
                            license_type=license_sources[src],
                            business_id=inspection.business_id,
                            license_number=None,
                            date_issued=today,
                            conditions=None,
                            paid=inspection.paid or False,
                        )
                        db.add(new_license)
                        db.commit()
                        db.refresh(new_license)
                        status_message = f"License created (#{new_license.id}). Expires {new_license.expiration_date.strftime('%Y-%m-%d')}." 
                        created_any = True

            # Attempt permit creation if license not created and it's a permit source
            if not created_any and is_permit_source:
                existing_permit = db.query(Permit).filter(Permit.inspection_id == inspection.id).first()
                if existing_permit:
                    status_message = status_message or f"Permit already exists (#{existing_permit.id})."
                else:
                    new_permit = Permit(
                        inspection_id=inspection.id,
                        permit_type=inspection.source,
                        business_id=getattr(inspection, "business_id", None),
                        paid=bool(getattr(inspection, "paid", False)),
                    )
                    db.add(new_permit)
                    db.commit()
                    db.refresh(new_permit)
                    status_message = f"Permit created (#{new_permit.id})."
                    created_any = True

            # If nothing created and no earlier status_message, supply explicit reason
            if not created_any and not status_message:
                if not (is_license_source or is_permit_source):
                    status_message = "Completed: source not eligible for license or permit creation."
                else:
                    # Fallback generic (should be rare if above branches set messages)
                    status_message = "Completed with no new records created."
    except Exception:
        db.rollback()
        if not status_message:
            status_message = "Status updated, but an error occurred during license/permit processing."

    # Re-load with relationships so response includes nested address/contact
    updated = (
        db.query(Inspection)
        .options(
            joinedload(Inspection.address),
            joinedload(Inspection.contact)
        )
        .filter(Inspection.id == inspection_id)
        .first()
    )
    # Return augmented object with status_message ephemeral field
    if updated:
        # Inject ephemeral field
        updated_dict = {k: getattr(updated, k) for k in updated.__dict__ if not k.startswith('_')}
        updated_dict['status_message'] = status_message
        return updated_dict
    return updated

# Update contact for an inspection (assign an existing contact)
@router.patch("/inspections/{inspection_id}/contact", response_model=InspectionResponse)
def update_inspection_contact(inspection_id: int, contact_id: int = Form(...), db: Session = Depends(get_db)):
    """
    Update the contact for an inspection.

    Args:
        inspection_id (int): The ID of the inspection.
        contact_id (int): The ID of the contact.
        db (Session): The database session.

    Returns:
        InspectionResponse: The updated inspection.

    Raises:
        HTTPException: If inspection or contact is not found.
    """
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    # Validate contact exists
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    inspection.contact_id = contact_id
    db.commit()

    updated = (
        db.query(Inspection)
        .options(
            joinedload(Inspection.address),
            joinedload(Inspection.contact)
        )
        .filter(Inspection.id == inspection_id)
        .first()
    )
    return updated

# Update inspector assignment for an inspection or complaint
@router.patch("/inspections/{inspection_id}/assignee", response_model=InspectionResponse)
def update_inspection_assignee(
    inspection_id: int,
    inspector_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Update the assigned inspector.

    Args:
        inspection_id (int): The ID of the inspection.
        inspector_id (int, optional): The ID of the inspector.
        db (Session): The database session.

    Returns:
        InspectionResponse: The updated inspection.

    Raises:
        HTTPException: If inspection or inspector is not found.
    """
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    previous_inspector_id = inspection.inspector_id
    if inspector_id in (None, ""):
        inspection.inspector_id = None
    else:
        inspector = db.query(User).filter(User.id == inspector_id).first()
        if not inspector:
            raise HTTPException(status_code=404, detail="User not found")
        inspection.inspector_id = inspector_id

    db.commit()

    # If assignment changed and new inspector exists, create notification
    if inspector_id and inspector_id != previous_inspector_id:
        _create_assignment_notification(db, inspection, inspector_id)

    updated = (
        db.query(Inspection)
        .options(
            joinedload(Inspection.address),
            joinedload(Inspection.contact),
            joinedload(Inspection.inspector),
        )
        .filter(Inspection.id == inspection_id)
        .first()
    )
    return updated
# Update schedule for an inspection
@router.patch("/inspections/{inspection_id}/schedule", response_model=InspectionResponse)
def update_inspection_schedule(
    inspection_id: int,
    scheduled_datetime: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Update inspection schedule.

    Args:
        inspection_id (int): The ID of the inspection.
        scheduled_datetime (str, optional): ISO-like datetime string.
        db (Session): The database session.

    Returns:
        InspectionResponse: The updated inspection.

    Raises:
        HTTPException: If inspection is not found or format is invalid.
    """
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    # Accept empty/None to clear
    if scheduled_datetime is None or scheduled_datetime == "":
        inspection.scheduled_datetime = None
    else:
        # Expect ISO-like format; support HTML datetime-local (YYYY-MM-DDTHH:MM)
        try:
            # datetime.fromisoformat handles both 'YYYY-MM-DDTHH:MM' and with seconds
            parsed = datetime.fromisoformat(scheduled_datetime)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid datetime format. Use YYYY-MM-DDTHH:MM")
        inspection.scheduled_datetime = parsed

    db.commit()

    updated = (
        db.query(Inspection)
        .options(
            joinedload(Inspection.address),
            joinedload(Inspection.contact)
        )
        .filter(Inspection.id == inspection_id)
        .first()
    )
    return updated

# Get all inspections for a specific Address
@router.get("/inspections/address/{address_id}", response_model=List[InspectionResponse])
def get_inspections_by_address(address_id: int, db: Session = Depends(get_db)):
    """
    Get all inspections for an address.

    Args:
        address_id (int): The ID of the address.
        db (Session): The database session.

    Returns:
        list[InspectionResponse]: A list of inspections.
    """
    inspections = (
      db.query(Inspection)
      .options(
        joinedload(Inspection.address),  # Eagerly load address relationship
        joinedload(Inspection.inspector)  # Eagerly load inspector relationship (User)
      )
      .filter(
      Inspection.address_id == address_id,
      Inspection.source != 'Complaint')
      .all()
    )
    return inspections

# Get all complaints for a specific Address
@router.get("/complaints/address/{address_id}", response_model=List[InspectionResponse])
def get_complaints_by_address(address_id: int, db: Session = Depends(get_db)):
    """
    Get all complaints for an address.

    Args:
        address_id (int): The ID of the address.
        db (Session): The database session.

    Returns:
        list[InspectionResponse]: A list of complaints.
    """
    complaints = (
      db.query(Inspection)
      .options(
        joinedload(Inspection.address),  # Eagerly load address relationship
        joinedload(Inspection.inspector)  # Eagerly load inspector relationship (User)
      )
      .filter(
      Inspection.address_id == address_id,
      Inspection.source == 'Complaint')
      .all()
    )
    return complaints

  
# Get all areas beloning to a specific inspection
@router.get("/inspections/{inspection_id}/areas", response_model=List[AreaResponse])
def get_areas_by_inspection(inspection_id: int, db: Session = Depends(get_db)):
    """
    Get all areas for an inspection.

    Args:
        inspection_id (int): The ID of the inspection.
        db (Session): The database session.

    Returns:
        list[AreaResponse]: A list of areas.
    """
    areas = db.query(Area).filter(Area.inspection_id == inspection_id
    ).order_by(Area.created_at.desc()).all()
    return areas

# Create a new area
@router.post("/inspections/{inspection_id}/areas", response_model=AreaResponse)
def create_area_for_inspection(inspection_id: int, area: AreaCreate, db: Session = Depends(get_db)):
    """
    Create a new area for an inspection.

    Args:
        inspection_id (int): The ID of the inspection.
        area (AreaCreate): Area data.
        db (Session): The database session.

    Returns:
        AreaResponse: The created area.

    Raises:
        HTTPException: If inspection is not found.
    """
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()

    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    # Create a new area and associate it with the inspection
    new_area = Area(**area.dict(), inspection_id=inspection_id)
    db.add(new_area)
    db.commit()
    db.refresh(new_area)

    return new_area

# Get all areas belonging to a specific unit
@router.get("/inspections/{inspection_id}/unit/{unit_id}/areas", response_model=List[AreaResponse])
def get_areas_by_unit(inspection_id: int, unit_id: int, db: Session = Depends(get_db)):
    """
    Get all areas for a specific unit within an inspection.

    Args:
        inspection_id (int): The ID of the inspection.
        unit_id (int): The ID of the unit.
        db (Session): The database session.

    Returns:
        list[AreaResponse]: A list of areas.
    """
    areas = db.query(Area).filter(Area.inspection_id == inspection_id, Area.unit_id == unit_id
    ).order_by(Area.created_at.desc()).all()
    return areas

# Create an area for a specific unit
@router.post("/inspections/{inspection_id}/unit/{unit_id}/areas", response_model=AreaResponse)
def create_area_for_unit(inspection_id: int, unit_id: int, area: AreaCreate, db: Session = Depends(get_db)):
    """
    Create an area for a specific unit within an inspection.

    Args:
        inspection_id (int): The ID of the inspection.
        unit_id (int): The ID of the unit.
        area (AreaCreate): Area data.
        db (Session): The database session.

    Returns:
        AreaResponse: The created area.

    Raises:
        HTTPException: If inspection is not found.
    """
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()

    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    # Create a new area and associate it with the inspection and unit
    area_data = area.dict(exclude_unset=True)
    area_data['inspection_id'] = inspection_id
    area_data['unit_id'] = unit_id
    new_area = Area(**area_data)
    db.add(new_area)
    db.commit()
    db.refresh(new_area)

    return new_area

# Get all areas for a specific inspection and unit
@router.get("/inspections/{inspection_id}/unit/{unit_id}/areas/count", response_model=int)
def get_area_count_by_unit_and_inspection(inspection_id: int, unit_id: int, db: Session = Depends(get_db)):
    """
    Count areas for a specific unit within an inspection.

    Args:
        inspection_id (int): The ID of the inspection.
        unit_id (int): The ID of the unit.
        db (Session): The database session.

    Returns:
        int: The count of areas.
    """
    area_count = db.query(Area).filter(Area.inspection_id == inspection_id, Area.unit_id == unit_id).count()
    return area_count

# Get all rooms
@router.get("/rooms/", response_model=List[RoomResponse])
def get_rooms(skip: int = 0, db: Session = Depends(get_db)):
    """
    Get all room types.

    Args:
        skip (int): Pagination offset.
        db (Session): The database session.

    Returns:
        list[RoomResponse]: A list of rooms.
    """
    rooms = db.query(Room).offset(skip).all()
    return rooms

# Create a new room
@router.post("/rooms/", response_model=RoomResponse)
def create_room(room: RoomCreate, db: Session = Depends(get_db)):
    """
    Create a new room type.

    Args:
        room (RoomCreate): Room data.
        db (Session): The database session.

    Returns:
        RoomResponse: The created room.
    """
    new_room = Room(**room.dict())
    db.add(new_room)
    db.commit()
    db.refresh(new_room)
    return new_room

# Show a room
@router.get("/rooms/{room_id}", response_model=RoomResponse)
def get_room(room_id: int, db: Session = Depends(get_db)):
    """
    Get a room type by ID.

    Args:
        room_id (int): The ID of the room.
        db (Session): The database session.

    Returns:
        RoomResponse: The room details.

    Raises:
        HTTPException: If room is not found.
    """
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room

# Edit a room
@router.put("/rooms/{room_id}", response_model=RoomResponse)
def update_room(room_id: int, room: RoomCreate, db: Session = Depends(get_db)):
    """
    Update a room type.

    Args:
        room_id (int): The ID of the room.
        room (RoomCreate): Updated room data.
        db (Session): The database session.

    Returns:
        RoomResponse: The updated room.

    Raises:
        HTTPException: If room is not found.
    """
    room_to_update = db.query(Room).filter(Room.id == room_id).first()
    if not room_to_update:
        raise HTTPException(status_code=404, detail="Room not found")
    room_data = room.dict()
    for key, value in room_data.items():
        setattr(room_to_update, key, value)
    db.commit()
    db.refresh(room_to_update)
    return room_to_update

# Delete a room
@router.delete("/rooms/{room_id}")
def delete_room(room_id: int, db: Session = Depends(get_db)):
    """
    Delete a room type.

    Args:
        room_id (int): The ID of the room.
        db (Session): The database session.

    Raises:
        HTTPException: If room is not found.
    """
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    db.delete(room)
    db.commit()
    return {"message": "Room deleted successfully"}

# Get all prompts for a specific Room
@router.get("/rooms/{room_id}/prompts", response_model=List[PromptResponse])
def get_prompts_by_room(room_id: int, db: Session = Depends(get_db)):
    """
    Get prompts for a specific room type.

    Args:
        room_id (int): The ID of the room.
        db (Session): The database session.

    Returns:
        list[PromptResponse]: A list of prompts.
    """
    prompts = db.query(Prompt).filter(Prompt.room_id == room_id).all()
    return prompts


# Create a new prompt
@router.post("/rooms/{room_id}/prompts", response_model=PromptResponse)
def create_prompt_for_room(room_id: int, prompt: PromptCreate, db: Session = Depends(get_db)):
    """
    Create a new prompt for a room type.

    Args:
        room_id (int): The ID of the room.
        prompt (PromptCreate): Prompt data.
        db (Session): The database session.

    Returns:
        PromptResponse: The created prompt.

    Raises:
        HTTPException: If room is not found.
    """
    room = db.query(Room).filter(Room.id == room_id).first()

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Create a new prompt and associate it with the room
    new_prompt = Prompt(**prompt.dict(), room_id=room_id)
    db.add(new_prompt)
    db.commit()
    db.refresh(new_prompt)

    return new_prompt

# Edit a prompt
@router.put("/prompts/{prompt_id}", response_model=PromptResponse)
def update_prompt(prompt_id: int, prompt: PromptCreate, db: Session = Depends(get_db)):
    """
    Update a prompt.

    Args:
        prompt_id (int): The ID of the prompt.
        prompt (PromptCreate): Updated prompt data.
        db (Session): The database session.

    Returns:
        PromptResponse: The updated prompt.

    Raises:
        HTTPException: If prompt is not found.
    """
    prompt_to_update = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt_to_update:
        raise HTTPException(status_code=404, detail="Prompt not found")
    prompt_data = prompt.dict()
    for key, value in prompt_data.items():
        setattr(prompt_to_update, key, value)
    db.commit()
    db.refresh(prompt_to_update)
    return prompt_to_update

# Delete a prompt
@router.delete("/prompts/{prompt_id}")
def delete_prompt(prompt_id: int, db: Session = Depends(get_db)):
    """
    Delete a prompt.

    Args:
        prompt_id (int): The ID of the prompt.
        db (Session): The database session.

    Raises:
        HTTPException: If prompt is not found.
    """
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    db.delete(prompt)
    db.commit()
    return {"message": "Prompt deleted successfully"}

# Get specific Area
@router.get("/areas/{area_id}", response_model=AreaResponse)
def get_area(area_id: int, db: Session = Depends(get_db)):
    """
    Get an area by ID.

    Args:
        area_id (int): The ID of the area.
        db (Session): The database session.

    Returns:
        AreaResponse: The area details.

    Raises:
        HTTPException: If area is not found.
    """
    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")
    return area

# Edit an area
@router.put("/areas/{area_id}", response_model=AreaResponse)
def update_area(area_id: int, area: AreaCreate, db: Session = Depends(get_db)):
    """
    Update an area.

    Args:
        area_id (int): The ID of the area.
        area (AreaCreate): Updated area data.
        db (Session): The database session.

    Returns:
        AreaResponse: The updated area.

    Raises:
        HTTPException: If area is not found.
    """
    area_to_update = db.query(Area).filter(Area.id == area_id).first()
    if not area_to_update:
        raise HTTPException(status_code=404, detail="Area not found")
    area_data = area.dict()
    for key, value in area_data.items():
        setattr(area_to_update, key, value)
    db.commit()
    db.refresh(area_to_update)
    return area_to_update

# Delete an area
@router.delete("/areas/{area_id}")
def delete_area(area_id: int, db: Session = Depends(get_db)):
    """
    Delete an area.

    Args:
        area_id (int): The ID of the area.
        db (Session): The database session.

    Raises:
        HTTPException: If area is not found.
    """
    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")
    db.delete(area)
    db.commit()
    return {"message": "Area deleted successfully"}

# Get all observations for a specific area
@router.get("/areas/{area_id}/observations", response_model=List[ObservationResponse])
def get_observations_for_area(area_id: int, db: Session = Depends(get_db)):
    """
    Get all observations for an area.

    Args:
        area_id (int): The ID of the area.
        db (Session): The database session.

    Returns:
        list[ObservationResponse]: A list of observations.
    """
    observations = (
        db.query(Observation)
        .options(
            joinedload(Observation.codes),
            joinedload(Observation.photos),
        )
        .filter(Observation.area_id == area_id)
        .all()
    )
    return observations

# Create a new observation for an area
@router.post("/areas/{area_id}/observations", response_model=ObservationResponse, status_code=status.HTTP_201_CREATED)
def create_observation_for_area(
    area_id: int,  # Path parameter is used directly here
    observation: ObservationCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new observation for an area.

    Args:
        area_id (int): The ID of the area.
        observation (ObservationCreate): Observation data.
        db (Session): The database session.

    Returns:
        ObservationResponse: The created observation.

    Raises:
        HTTPException: If area is not found.
    """
    # Create the observation entry in the database
    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")

    # Persist observation with required user_id
    new_observation = Observation(
        content=observation.content,
        area_id=area_id,  # Use area_id from the URL
        potentialvio=observation.potentialvio,
        user_id=observation.user_id,
    )
    db.add(new_observation)
    db.commit()
    db.refresh(new_observation)
    # Attach suspected codes if provided
    if observation.codes:
        codes = db.query(Code).filter(Code.id.in_(observation.codes)).all()
        new_observation.codes = codes
        db.commit()
        db.refresh(new_observation)

    return new_observation


@router.patch("/observations/{observation_id}", response_model=ObservationResponse)
def update_observation(observation_id: int, payload: ObservationUpdate, db: Session = Depends(get_db)):
    """
    Update an observation.

    Args:
        observation_id (int): The ID of the observation.
        payload (ObservationUpdate): Updated data.
        db (Session): The database session.

    Returns:
        ObservationResponse: The updated observation.

    Raises:
        HTTPException: If observation is not found.
    """
    obs = (
        db.query(Observation)
        .options(joinedload(Observation.codes), joinedload(Observation.photos))
        .filter(Observation.id == observation_id)
        .first()
    )
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")

    data = payload.dict(exclude_unset=True)
    # Update simple fields
    if 'content' in data and data['content'] is not None:
        obs.content = data['content']
    if 'potentialvio' in data and data['potentialvio'] is not None:
        obs.potentialvio = data['potentialvio']
    # Update suspected codes if provided
    if 'codes' in data and data['codes'] is not None:
        codes = db.query(Code).filter(Code.id.in_(data['codes'] or [])).all()
        obs.codes = codes

    db.commit()
    db.refresh(obs)
    return obs


# Upload photos for an observation
@router.post("/observations/{observation_id}/photos", status_code=status.HTTP_201_CREATED)
async def upload_photos_for_observation(
    observation_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload one or more image files for an observation and persist a Photo row per file.

    Args:
        observation_id (int): The ID of the observation.
        files (list[UploadFile]): List of files to upload.
        db (Session): The database session.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: If observation is not found or upload fails.
    """
    observation = db.query(Observation).filter(Observation.id == observation_id).first()
    if not observation:
        raise HTTPException(status_code=404, detail="Observation not found")

    for file in files:
        try:
            raw = await file.read()
            normalized_bytes, norm_filename, norm_ct = normalize_image_for_web(raw, file.filename, file.content_type)
            blob_name = f"observations/{observation_id}/{uuid.uuid4()}-{norm_filename}"
            blob_client = storage.blob_service_client.get_blob_client(container=storage.CONTAINER_NAME, blob=blob_name)
            blob_client.upload_blob(normalized_bytes, overwrite=True, content_type=norm_ct)

            # Persist photo record referencing the uploaded blob
            photo_url = f"https://{storage.account_name}.blob.core.windows.net/{storage.CONTAINER_NAME}/{blob_name}"
            db_photo = Photo(url=photo_url, observation_id=observation_id)
            db.add(db_photo)
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to upload file {file.filename}: {str(e)}")

    db.commit()
    return {"detail": "Photos uploaded successfully"}

    

# Upload photos for an inspection (used for complaints)
@router.post("/inspections/{inspection_id}/photos", status_code=status.HTTP_201_CREATED)
async def upload_photos_for_inspection(
    inspection_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload photos for an inspection (e.g., complaint).

    Args:
        inspection_id (int): The ID of the inspection.
        files (list[UploadFile]): List of files to upload.
        db (Session): The database session.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: If inspection is not found or upload fails.
    """
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    for file in files:
        try:
            raw = await file.read()
            normalized_bytes, norm_filename, norm_ct = normalize_image_for_web(raw, file.filename, file.content_type)
            blob_key = f"inspections/{inspection_id}/{uuid.uuid4()}-{norm_filename}"
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
                record_type="Inspection",
                record_id=inspection_id,
                blob_id=blob_row.id,
                created_at=datetime.utcnow(),
            )
            db.add(attachment_row)
            db.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload file {file.filename}: {str(e)}")

    return {"detail": "Photos uploaded successfully"}

# List all potential violations (observations flagged potential) for an inspection
@router.get("/inspections/{inspection_id}/potential-observations", response_model=List[PotentialObservationResponse])
def get_potential_observations_for_inspection(inspection_id: int, db: Session = Depends(get_db)):
    """
    Get all potential violations (flagged observations) for an inspection.

    Args:
        inspection_id (int): The ID of the inspection.
        db (Session): The database session.

    Returns:
        list[PotentialObservationResponse]: A list of potential observations.

    Raises:
        HTTPException: If inspection is not found.
    """
    # Ensure inspection exists
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    # Join Observations -> Area -> Unit to provide context
    observations = (
        db.query(Observation, Area)
        .options(
            joinedload(Observation.codes),
            joinedload(Observation.photos),
        )
        .join(Area, Observation.area_id == Area.id)
        .filter(Area.inspection_id == inspection_id, Observation.potentialvio == True)
        .order_by(Observation.created_at.desc())
        .all()
    )

    results: List[PotentialObservationResponse] = []
    for obs, area in observations:
        unit_number = None
        if area.unit_id:
            # Lazy fetch unit number to avoid heavy join; small per-item overhead acceptable here
            from models import Unit  # local import to avoid circular
            unit = db.query(Unit).filter(Unit.id == area.unit_id).first()
            unit_number = unit.number if unit else None
        results.append(PotentialObservationResponse(
            id=obs.id,
            content=obs.content,
            area_id=obs.area_id,
            user_id=obs.user_id,
            potentialvio=obs.potentialvio,
            created_at=obs.created_at,
            updated_at=obs.updated_at,
            inspection_id=area.inspection_id,
            area_name=area.name,
            unit_id=area.unit_id,
            unit_number=unit_number,
            codes=obs.codes,
            photos=obs.photos,
        ))

    return results

    db.commit()

    return {"detail": "Photos uploaded successfully"}

# Get attachments for an inspection (complaint)
@router.get("/inspections/{inspection_id}/photos")
def get_inspection_photos(inspection_id: int, download: bool = False, db: Session = Depends(get_db)):
    """
    Get signed URLs for photos attached to an inspection.

    Args:
        inspection_id (int): The ID of the inspection.
        download (bool): Download flag.
        db (Session): The database session.

    Returns:
        list[dict]: Photo details.
    """
    attachments = db.query(ActiveStorageAttachment).filter(
        ActiveStorageAttachment.record_id == inspection_id,
        ActiveStorageAttachment.record_type == 'Inspection',
        ActiveStorageAttachment.name == 'photos',
    ).all()

    results = []
    for attachment in attachments:
        blob = db.query(ActiveStorageBlob).filter(ActiveStorageBlob.id == attachment.blob_id).first()
        if not blob:
            continue
        try:
            # Ensure browser-safe; convert on-demand if needed
            blob = ensure_blob_browser_safe(db, blob)
            # Ensure storage clients/account metadata are initialized before SAS generation
            try:
                storage.ensure_initialized()
            except Exception:
                # allow SAS generation to fail below; we'll catch and skip
                pass
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
            })
        except Exception:
            continue

    return results

# --- Inspection comments endpoints ---
@router.get("/inspections/{inspection_id}/comments", response_model=List[InspectionCommentResponse])
def get_inspection_comments(inspection_id: int, db: Session = Depends(get_db)):
    """
    Get all comments for an inspection.

    Args:
        inspection_id (int): The ID of the inspection.
        db (Session): The database session.

    Returns:
        list[InspectionCommentResponse]: A list of inspection comments.

    Raises:
        HTTPException: If inspection is not found.
    """
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    comments = (
        db.query(InspectionComment)
        .filter(InspectionComment.inspection_id == inspection_id)
        .order_by(InspectionComment.created_at.desc())
        .all()
    )

    if not comments:
        return []

    # Batch related lookups to include mentions and contact mentions in the response
    comment_ids = {int(c.id) for c in comments}
    user_ids = {int(c.user_id) for c in comments if c.user_id is not None}

    users_by_id = {}
    if user_ids:
        for u in db.query(User).filter(User.id.in_(list(user_ids))).all():
            users_by_id[int(u.id)] = u

    # Fetch user mentions per comment
    mentions_by_comment: dict[int, list[User]] = {cid: [] for cid in comment_ids}
    try:
        if comment_ids:
            from models import Mention

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

    # Fetch contact mentions per comment
    contact_mentions_by_comment: dict[int, list[Contact]] = {cid: [] for cid in comment_ids}
    try:
        if comment_ids:
            from models import CommentContactLink, Contact

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

    results = []
    for c in comments:
        user = users_by_id.get(int(c.user_id)) if c.user_id is not None else None
        user_mentions = mentions_by_comment.get(int(c.id), [])
        contact_mentions = contact_mentions_by_comment.get(int(c.id), [])
        results.append(
            InspectionCommentResponse(
                id=c.id,
                inspection_id=c.inspection_id,
                content=c.content,
                user_id=c.user_id,
                user=UserResponse.from_orm(user) if user else None,
                mentions=[UserResponse.from_orm(u) for u in user_mentions] if user_mentions else None,
                contact_mentions=[ContactResponse.from_orm(ct) for ct in contact_mentions] if contact_mentions else None,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
        )

    return results

@router.post("/inspections/{inspection_id}/comments", response_model=InspectionCommentResponse, status_code=status.HTTP_201_CREATED)
def create_inspection_comment(
    inspection_id: int,
    content: str = Form(...),
    user_id: int = Form(...),
    mentioned_user_ids: Optional[str] = Form(None),
    mentioned_contact_ids: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Create a comment for an inspection.

    Args:
        inspection_id (int): The ID of the inspection.
        content (str): Comment content.
        user_id (int): User ID.
        mentioned_user_ids (str, optional): Mentioned user IDs.
        mentioned_contact_ids (str, optional): Mentioned contact IDs.
        db (Session): The database session.

    Returns:
        InspectionCommentResponse: The created comment.

    Raises:
        HTTPException: If inspection or user is not found.
    """
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    # Validate user exists (best-effort)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    comment = InspectionComment(
        user_id=user_id,
        inspection_id=inspection_id,
        content=content,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    # Handle mentions in the comment (users and contacts) using shared helpers
    try:
        # create notifications and Mention rows for @-mentions (usernames or explicit ids)
        # Use any explicit ids sent from the client first; otherwise fallback to parsing tokens in content
        _handle_user_mentions(
            db=db,
            comment_id=comment.id,
            actor_id=comment.user_id,
            content=comment.content,
            raw_ids=mentioned_user_ids,
            context_label="inspection comment",
        )

        # collect contact ids from explicit form value or parse %tokens in content
        contact_ids = _collect_contact_ids(db, mentioned_contact_ids, comment.content)
        if contact_ids:
            _store_contact_mentions(db, comment.id, comment.user_id, contact_ids)
    except Exception:
        # Mention handling should not block primary flow
        pass

    # Build response including mention lists so clients can render badges without extra fetches
    try:
        user = db.query(User).filter(User.id == comment.user_id).first() if comment.user_id else None
        try:
            from models import Mention

            user_mentions = (
                db.query(User)
                .join(Mention, Mention.user_id == User.id)
                .filter(Mention.comment_id == comment.id)
                .all()
            )
        except Exception:
            user_mentions = []
        contact_mentions = _get_contact_mentions(db, comment.id)
        response = InspectionCommentResponse(
            id=comment.id,
            inspection_id=comment.inspection_id,
            content=comment.content,
            user_id=comment.user_id,
            user=UserResponse.from_orm(user) if user else None,
            mentions=[UserResponse.from_orm(u) for u in user_mentions] if user_mentions else None,
            contact_mentions=[ContactResponse.from_orm(c) for c in contact_mentions] if contact_mentions else None,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
        )
        return response
    except Exception:
        # Fallback: return raw ORM object if building the response fails
        return comment


