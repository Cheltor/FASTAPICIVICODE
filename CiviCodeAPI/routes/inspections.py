from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from models import Inspection, Contact, Address, Area, Room, Prompt, Observation, Photo, ActiveStorageAttachment, ActiveStorageBlob
from schemas import InspectionResponse, ContactResponse, AddressResponse, AreaResponse, AreaCreate, RoomResponse, RoomCreate, PromptCreate, PromptResponse, ObservationCreate, ObservationResponse
from database import get_db
from storage import blob_service_client, CONTAINER_NAME, account_name, account_key
from datetime import datetime, timedelta
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
import uuid

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
    db: Session = Depends(get_db)
):
    new_inspection = Inspection(
        address_id=address_id,
        unit_id=unit_id,
        source=source,
        description=description,
        contact_id=contact_id,
        paid=paid
    )
    db.add(new_inspection)
    db.commit()
    db.refresh(new_inspection)

    for attachment in attachments:
        try:
            content_bytes = await attachment.read()
            blob_key = f"inspections/{new_inspection.id}/{uuid.uuid4()}-{attachment.filename}"
            blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=blob_key)
            blob_client.upload_blob(content_bytes, overwrite=True, content_type=attachment.content_type)

            blob_row = ActiveStorageBlob(
                key=blob_key,
                filename=attachment.filename,
                content_type=attachment.content_type,
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
    return inspection

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
    observations = db.query(Observation).filter(Observation.area_id == area_id).all()
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

    new_observation = Observation(
        content=observation.content,
        area_id=area_id,  # Use area_id from the URL
        potentialvio=observation.potentialvio
    )
    db.add(new_observation)
    db.commit()
    db.refresh(new_observation)

    return new_observation



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
        blob_name = f"{uuid.uuid4()}-{file.filename}"
        blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)

        try:
            blob_client.upload_blob(file.file, overwrite=True)
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
            content_bytes = await file.read()
            blob_key = f"inspections/{inspection_id}/{uuid.uuid4()}-{file.filename}"
            blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=blob_key)
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
            results.append({
                "filename": blob.filename,
                "content_type": blob.content_type,
                "url": url,
            })
        except Exception:
            continue

    return results
