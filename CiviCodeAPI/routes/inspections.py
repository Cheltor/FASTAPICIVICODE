from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from typing import List
from models import Inspection, Contact, Address, Area, Room, Prompt, Observation, Photo
from schemas import InspectionCreate, InspectionResponse, ContactResponse, AddressResponse, AreaResponse, AreaCreate, RoomResponse, RoomCreate, PromptCreate, PromptResponse, ObservationCreate, ObservationResponse
from database import get_db
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from dotenv import load_dotenv
import os 
import uuid


router = APIRouter()

# Load the environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path=env_path)

connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

# Initialize the Azure Blob Storage client
connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
blob_service_client = BlobServiceClient.from_connection_string(connection_string)

container_name = "civicodephotos"

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
def create_inspection(inspection: InspectionCreate, db: Session = Depends(get_db)):
    new_inspection = Inspection(**inspection.dict())
    db.add(new_inspection)
    db.commit()
    db.refresh(new_inspection)
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
        user_id=observation.user_id,
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
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

        try:
            blob_client.upload_blob(file.file, overwrite=True)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload file {file.filename}: {str(e)}")

        photo_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{blob_name}"

        db_photo = Photo(url=photo_url, observation_id=observation_id)
        db.add(db_photo)

    db.commit()

    return {"detail": "Photos uploaded successfully"}
