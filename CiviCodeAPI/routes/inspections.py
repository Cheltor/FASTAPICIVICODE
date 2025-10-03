from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from models import Inspection, Contact, Address, Area, Room, Prompt, Observation, Photo, ActiveStorageAttachment, ActiveStorageBlob, License, Permit, Violation, User
from schemas import InspectionResponse, ContactResponse, AddressResponse, AreaResponse, AreaCreate, RoomResponse, RoomCreate, PromptCreate, PromptResponse, ObservationCreate, ObservationResponse, ObservationUpdate
from schemas import InspectionResponse, ContactResponse, AddressResponse, AreaResponse, AreaCreate, RoomResponse, RoomCreate, PromptCreate, PromptResponse, ObservationCreate, ObservationResponse, PotentialObservationResponse
from database import get_db
from models import Code
from storage import blob_service_client, CONTAINER_NAME, account_name, account_key
from image_utils import normalize_image_for_web
from datetime import datetime, timedelta, date
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
import uuid
from media_service import ensure_blob_browser_safe

router = APIRouter()

# Get all inspections
@router.get("/inspections/", response_model=List[InspectionResponse])
def get_inspections(skip: int = 0, db: Session = Depends(get_db)):
    inspections = db.query(Inspection).filter(Inspection.source != 'Complaint').order_by(Inspection.created_at.desc()).offset(skip).all()
    return inspections

# Get all complaints
@router.get("/complaints/", response_model=List[InspectionResponse])
def get_complaints(skip: int = 0, db: Session = Depends(get_db)):
    complaints = db.query(Inspection).filter(Inspection.source == 'Complaint').order_by(Inspection.created_at.desc()).offset(skip).all()
    return complaints

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
    db: Session = Depends(get_db)
):
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
            blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=blob_key)
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

    return new_inspection

# Get a specific inspection by ID
@router.get("/inspections/{inspection_id}", response_model=InspectionResponse)
def get_inspection(inspection_id: int, db: Session = Depends(get_db)):
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
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    if inspector_id in (None, ""):
        inspection.inspector_id = None
    else:
        inspector = db.query(User).filter(User.id == inspector_id).first()
        if not inspector:
            raise HTTPException(status_code=404, detail="User not found")
        inspection.inspector_id = inspector_id

    db.commit()

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
    areas = db.query(Area).filter(Area.inspection_id == inspection_id
    ).order_by(Area.created_at.desc()).all()
    return areas

# Create a new area
@router.post("/inspections/{inspection_id}/areas", response_model=AreaResponse)
def create_area_for_inspection(inspection_id: int, area: AreaCreate, db: Session = Depends(get_db)):
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
    areas = db.query(Area).filter(Area.inspection_id == inspection_id, Area.unit_id == unit_id
    ).order_by(Area.created_at.desc()).all()
    return areas

# Create an area for a specific unit
@router.post("/inspections/{inspection_id}/unit/{unit_id}/areas", response_model=AreaResponse)
def create_area_for_unit(inspection_id: int, unit_id: int, area: AreaCreate, db: Session = Depends(get_db)):
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
    area_count = db.query(Area).filter(Area.inspection_id == inspection_id, Area.unit_id == unit_id).count()
    return area_count

# Get all rooms
@router.get("/rooms/", response_model=List[RoomResponse])
def get_rooms(skip: int = 0, db: Session = Depends(get_db)):
    rooms = db.query(Room).offset(skip).all()
    return rooms

# Create a new room
@router.post("/rooms/", response_model=RoomResponse)
def create_room(room: RoomCreate, db: Session = Depends(get_db)):
    new_room = Room(**room.dict())
    db.add(new_room)
    db.commit()
    db.refresh(new_room)
    return new_room

# Show a room
@router.get("/rooms/{room_id}", response_model=RoomResponse)
def get_room(room_id: int, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room

# Edit a room
@router.put("/rooms/{room_id}", response_model=RoomResponse)
def update_room(room_id: int, room: RoomCreate, db: Session = Depends(get_db)):
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
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    db.delete(room)
    db.commit()
    return {"message": "Room deleted successfully"}

# Get all prompts for a specific Room
@router.get("/rooms/{room_id}/prompts", response_model=List[PromptResponse])
def get_prompts_by_room(room_id: int, db: Session = Depends(get_db)):
    prompts = db.query(Prompt).filter(Prompt.room_id == room_id).all()
    return prompts


# Create a new prompt
@router.post("/rooms/{room_id}/prompts", response_model=PromptResponse)
def create_prompt_for_room(room_id: int, prompt: PromptCreate, db: Session = Depends(get_db)):
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
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    db.delete(prompt)
    db.commit()
    return {"message": "Prompt deleted successfully"}

# Get specific Area
@router.get("/areas/{area_id}", response_model=AreaResponse)
def get_area(area_id: int, db: Session = Depends(get_db)):
    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")
    return area

# Edit an area
@router.put("/areas/{area_id}", response_model=AreaResponse)
def update_area(area_id: int, area: AreaCreate, db: Session = Depends(get_db)):
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
    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")
    db.delete(area)
    db.commit()
    return {"message": "Area deleted successfully"}

# Get all observations for a specific area
@router.get("/areas/{area_id}/observations", response_model=List[ObservationResponse])
def get_observations_for_area(area_id: int, db: Session = Depends(get_db)):
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
    observation = db.query(Observation).filter(Observation.id == observation_id).first()
    if not observation:
        raise HTTPException(status_code=404, detail="Observation not found")
    
    for file in files:
        try:
            raw = await file.read()
            normalized_bytes, norm_filename, norm_ct = normalize_image_for_web(raw, file.filename, file.content_type)
            blob_name = f"observations/{observation_id}/{uuid.uuid4()}-{norm_filename}"
            blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
            blob_client.upload_blob(normalized_bytes, overwrite=True, content_type=norm_ct)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload file {file.filename}: {str(e)}")

        photo_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{CONTAINER_NAME}/{blob_name}"

        db_photo = Photo(url=photo_url, observation_id=observation_id)
        db.add(db_photo)

    db.commit()

    return {"detail": "Photos uploaded successfully"}

    

# Upload photos for an inspection (used for complaints)
@router.post("/inspections/{inspection_id}/photos", status_code=status.HTTP_201_CREATED)
async def upload_photos_for_inspection(
    inspection_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    for file in files:
        try:
            raw = await file.read()
            normalized_bytes, norm_filename, norm_ct = normalize_image_for_web(raw, file.filename, file.content_type)
            blob_key = f"inspections/{inspection_id}/{uuid.uuid4()}-{norm_filename}"
            blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=blob_key)
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
            sas_token = generate_blob_sas(
                account_name=account_name,
                container_name=CONTAINER_NAME,
                blob_name=blob.key,
                account_key=account_key,
                permission=BlobSasPermissions(read=True),
                start=datetime.utcnow() - timedelta(minutes=5),
                expiry=datetime.utcnow() + timedelta(hours=1),
                content_disposition=(f'attachment; filename="{blob.filename}"' if download else None),
            )
            url = f"https://{account_name}.blob.core.windows.net/{CONTAINER_NAME}/{blob.key}?{sas_token}"
            poster_url = None
            if (blob.content_type or "").startswith("video/") and blob.key.lower().endswith('.mp4'):
                base = blob.key[:-4]
                poster_key = f"{base}-poster.jpg"
                try:
                    poster_sas = generate_blob_sas(
                        account_name=account_name,
                        container_name=CONTAINER_NAME,
                        blob_name=poster_key,
                        account_key=account_key,
                        permission=BlobSasPermissions(read=True),
                        start=datetime.utcnow() - timedelta(minutes=5),
                        expiry=datetime.utcnow() + timedelta(hours=1),
                    )
                    poster_url = f"https://{account_name}.blob.core.windows.net/{CONTAINER_NAME}/{poster_key}?{poster_sas}"
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


