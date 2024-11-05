from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List
from models import Address, Comment, Violation, Inspection, Unit
from schemas import AddressCreate, AddressResponse, CommentResponse, ViolationResponse, InspectionResponse, ViolationCreate, CommentCreate, InspectionCreate, UnitResponse, UnitCreate
from database import get_db  # Assuming a get_db function is set up to provide the database session
from sqlalchemy import or_

# Create a router instance
router = APIRouter()

# Get all addresses
@router.get("/addresses/", response_model=List[AddressResponse])
def get_addresses(skip: int = 0, db: Session = Depends(get_db)):
  addresses = db.query(Address).order_by(Address.id).offset(skip).all()
  return addresses

# Search for addresses by partial match of combadd, with a limit on results
@router.get("/addresses/search", response_model=List[AddressResponse])
def search_addresses(
    query: str = Query(..., description="Search term for address combadd or property name"),
    limit: int = Query(5, ge=1, le=50, description="Limit the number of results"),
    db: Session = Depends(get_db)
):
    # Perform a case-insensitive search on combadd or property_name using the query parameter
    addresses = (
        db.query(Address)
        .filter(
            or_(
                Address.combadd.ilike(f"%{query}%"),    # Search by combadd
                Address.property_name.ilike(f"%{query}%")  # Search by property_name
            )
        )
        .limit(limit)
        .all()
    )
    return addresses

# Get a single address by ID
@router.get("/addresses/{address_id}", response_model=AddressResponse)
def get_address(address_id: int, db: Session = Depends(get_db)):
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    return address

# Create a new address
@router.post("/addresses/", response_model=AddressResponse)
def create_address(address: AddressCreate, db: Session = Depends(get_db)):
    new_address = Address(**address.dict())
    db.add(new_address)
    db.commit()
    db.refresh(new_address)
    return new_address

# Update an existing address
@router.put("/addresses/{address_id}", response_model=AddressResponse)
def update_address(address_id: int, address: AddressCreate, db: Session = Depends(get_db)):
    existing_address = db.query(Address).filter(Address.id == address_id).first()
    if not existing_address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    for key, value in address.dict().items():
        setattr(existing_address, key, value)
    
    db.commit()
    db.refresh(existing_address)
    return existing_address

# Delete an address
@router.delete("/addresses/{address_id}", response_model=AddressResponse)
def delete_address(address_id: int, db: Session = Depends(get_db)):
    address = db.query

# Show the comments for the address
@router.get("/addresses/{address_id}/comments", response_model=List[CommentResponse])
def get_address_comments(address_id: int, db: Session = Depends(get_db)):
    # Query the comments for the given address ID and order by created_at descending
    comments = db.query(Comment).filter(Comment.address_id == address_id).order_by(Comment.created_at.desc()).all()
    if not comments:
        raise HTTPException(status_code=404, detail="No comments found for this address")
    return comments

# Add a comment to the address
@router.post("/addresses/{address_id}/comments", response_model=CommentResponse)
def create_comment_for_address(address_id: int, comment: CommentCreate, db: Session = Depends(get_db)):
    # Create and save the comment
    new_comment = Comment(address_id=address_id, **comment.dict())
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment

# Update a comment for the address
@router.put("/addresses/{address_id}/comments/{comment_id}", response_model=CommentResponse)
def update_address_comment(address_id: int, comment_id: int, comment: CommentResponse, db: Session = Depends(get_db)):
    # Check if the address exists
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Check if the comment exists
    existing_comment = db.query(Comment).filter(Comment.id == comment_id, Comment.address_id == address_id).first()
    if not existing_comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Update the comment
    for key, value in comment.dict().items():
        setattr(existing_comment, key, value)
    
    db.commit()
    db.refresh(existing_comment)
    return existing_comment

# Delete a comment for the address
@router.delete("/addresses/{address_id}/comments/{comment_id}", response_model=CommentResponse)
def delete_address_comment(address_id: int, comment_id: int, db: Session = Depends(get_db)):
    # Check if the address exists
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Check if the comment exists
    existing_comment = db.query(Comment).filter(Comment.id == comment_id, Comment.address_id == address_id).first()
    if not existing_comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Delete the comment
    db.delete(existing_comment)
    db.commit()
    return existing_comment

# Show the violations for the address
@router.get("/addresses/{address_id}/violations", response_model=List[ViolationResponse])
def get_address_violations(address_id: int, db: Session = Depends(get_db)):
    # Query the violations for the given address ID and order by created_at descending
    violations = db.query(Violation).filter(Violation.address_id == address_id).order_by(Violation.created_at.desc()).all()
    if not violations:
        raise HTTPException(status_code=404, detail="No violations found for this address")
    return violations

# Add a violation to the address
@router.post("/addresses/{address_id}/violations", response_model=ViolationResponse)
def add_address_violation(address_id: int, violation: ViolationResponse, db: Session = Depends(get_db)):
    # Check if the address exists
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Create a new violation
    new_violation = Violation(**violation.dict(), address_id=address_id)
    db.add(new_violation)
    db.commit()
    db.refresh(new_violation)
    return new_violation

# Update a violation for the address
@router.put("/addresses/{address_id}/violations/{violation_id}", response_model=ViolationResponse)
def update_address_violation(address_id: int, violation_id: int, violation: ViolationResponse, db: Session = Depends(get_db)):
    # Check if the address exists
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Check if the violation exists
    existing_violation = db.query(Violation).filter(Violation.id == violation_id, Violation.address_id == address_id).first()
    if not existing_violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    
    # Update the violation
    for key, value in violation.dict().items():
        setattr(existing_violation, key, value)
    
    db.commit()
    db.refresh(existing_violation)
    return existing_violation

# Delete a violation for the address
@router.delete("/addresses/{address_id}/violations/{violation_id}", response_model=ViolationResponse)
def delete_address_violation(address_id: int, violation_id: int, db: Session = Depends(get_db)):
    # Check if the address exists
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Check if the violation exists
    existing_violation = db.query(Violation).filter(Violation.id == violation_id, Violation.address_id == address_id).first()
    if not existing_violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    
    # Delete the violation
    db.delete(existing_violation)
    db.commit()
    return existing_violation

# Show the inspections for the address
@router.get("/addresses/{address_id}/inspections", response_model=List[InspectionResponse])
def get_address_inspections(address_id: int, db: Session = Depends(get_db)):
    # Query the inspections for the given address ID and order by created_at descending
    inspections = db.query(Inspection).filter(
        Inspection.address_id == address_id,
        Inspection.source != 'Complaint'
    ).order_by(Inspection.created_at.desc()).all()
    if not inspections:
        raise HTTPException(status_code=404, detail="No inspections found for this address")
    return inspections

# Add an inspection to the address
@router.post("/addresses/{address_id}/inspections", response_model=InspectionResponse)
def add_address_inspection(address_id: int, inspection: InspectionResponse, db: Session = Depends(get_db)):
    # Check if the address exists
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Create a new inspection
    new_inspection = Inspection(**inspection.dict(), address_id=address_id)
    db.add(new_inspection)
    db.commit()
    db.refresh(new_inspection)
    return

# Update an inspection for the address
@router.put("/addresses/{address_id}/inspections/{inspection_id}", response_model=InspectionResponse)
def update_address_inspection(address_id: int, inspection_id: int, inspection: InspectionResponse, db: Session = Depends(get_db)):
    # Check if the address exists
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Check if the inspection exists
    existing_inspection = db.query(Inspection).filter(Inspection.id == inspection_id, Inspection.address_id == address_id).first()
    if not existing_inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    # Update the inspection
    for key, value in inspection.dict().items():
        setattr(existing_inspection, key, value)
    
    db.commit()
    db.refresh(existing_inspection)
    return existing_inspection

# Delete an inspection for the address
@router.delete("/addresses/{address_id}/inspections/{inspection_id}", response_model=InspectionResponse)
def delete_address_inspection(address_id: int, inspection_id: int, db: Session = Depends(get_db)):
    # Check if the address exists
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Check if the inspection exists
    existing_inspection = db.query(Inspection).filter(Inspection.id == inspection_id, Inspection.address_id == address_id).first()
    if not existing_inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    # Delete the inspection
    db.delete(existing_inspection)
    db.commit()
    return existing_inspection

# Show all the units for the address
@router.get("/addresses/{address_id}/units", response_model=List[UnitResponse])
def get_address_units(address_id: int, db: Session = Depends(get_db)):
    # Query the units for the given address ID and order by created_at descending
    units = db.query(Unit).filter(Unit.address_id == address_id).order_by(Unit.created_at.desc()).all()
    
    # Return the units (it will be an empty list if no units are found)
    return units  # No need to raise an exception; an empty list will be returned if no units exist

# Add a unit to the address
@router.post("/addresses/{address_id}/units", response_model=UnitResponse)
def create_unit(address_id: int, unit: UnitCreate, db: Session = Depends(get_db)):
    # Check if the address exists
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Create a new unit
    new_unit = Unit(**unit.dict(), address_id=address_id)
    db.add(new_unit)
    db.commit()
    db.refresh(new_unit)
    return new_unit

# Unit information
@router.get("/units/{unit_id}", response_model=UnitResponse)
def get_unit(unit_id: int, db: Session = Depends(get_db)):
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    return unit

# Get units by address ID
@router.get("/units", response_model=List[UnitResponse])
def get_units_by_address_id(address_id: int, db: Session = Depends(get_db)):
    units = db.query(Unit).filter(Unit.address_id == address_id).order_by(Unit.created_at.desc()).all()
    if not units:
        raise HTTPException(status_code=404, detail="No units found for this address")
    return units