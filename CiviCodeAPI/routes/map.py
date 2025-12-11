from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Any
from database import get_db
from models import Inspection, Violation, Address
from pydantic import BaseModel

router = APIRouter(prefix="/map", tags=["map"])

class MapMarker(BaseModel):
    id: str  # globally unique ID for frontend key, e.g. "inspection-1"
    entity_id: int
    address_id: int # ID of the Address record
    type: str # 'inspection', 'violation'
    lat: float
    lng: float
    status: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    assigned_user_id: Optional[int] = None
    assigned_user_name: Optional[str] = None
    violation_type: Optional[str] = None
    deadline: Optional[str] = None

@router.get("/markers", response_model=List[MapMarker])
def get_map_markers(
    db: Session = Depends(get_db),
    include_closed: bool = Query(False, description="Include closed cases"),
    show_all_properties: bool = Query(False, description="Include all properties (Admin only)")
):
    markers = []
    active_address_ids = set()

    # 1. Fetch Inspections with coordinates
    inspections_query = (
        db.query(Inspection)
        .join(Inspection.address)
        .filter(Address.latitude != None, Address.longitude != None)
    )
    
    if not include_closed:
        inspections_query = inspections_query.filter(
            Inspection.status.notin_(["Closed", "Completed", "Canceled"])
        )

    inspections = inspections_query.options(
        joinedload(Inspection.address),
        joinedload(Inspection.inspector)
    ).all()

    for insp in inspections:
        active_address_ids.add(insp.address_id)
        markers.append(MapMarker(
            id=f"inspection-{insp.id}",
            entity_id=insp.id,
            address_id=insp.address_id,
            type="inspection",
            lat=insp.address.latitude,
            lng=insp.address.longitude,
            status=insp.status,
            address=insp.address.combadd,
            description=insp.description or insp.source,
            severity=insp.severity,
            assigned_user_id=insp.inspector_id,
            assigned_user_name=insp.inspector.name if insp.inspector else "Unassigned"
        ))

    # 2. Fetch Violations with coordinates
    violations_query = (
        db.query(Violation)
        .join(Violation.address)
        .filter(Address.latitude != None, Address.longitude != None)
    )

    if not include_closed:
        violations_query = violations_query.filter(Violation.closed_at == None)

    violations = violations_query.options(
        joinedload(Violation.address),
        joinedload(Violation.user)
    ).all()

    for vio in violations:
        active_address_ids.add(vio.address_id)
        
        # Calculate deadline safely
        deadline_str = None
        try:
            if vio.deadline_date:
                deadline_str = vio.deadline_date.strftime("%Y-%m-%d")
        except:
            pass

        markers.append(MapMarker(
            id=f"violation-{vio.id}",
            entity_id=vio.id,
            address_id=vio.address_id,
            type="violation",
            lat=vio.address.latitude,
            lng=vio.address.longitude,
            status=str(vio.status),
            address=vio.address.combadd,
            description=vio.description or vio.violation_type,
            severity=None,
            assigned_user_id=vio.user_id,
            assigned_user_name=vio.user.name if vio.user else "System",
            violation_type=vio.violation_type,
            deadline=deadline_str
        ))

    # 3. Fetch specific Addresses if requested
    if show_all_properties:
        properties_query = (
            db.query(Address)
            .filter(Address.latitude != None, Address.longitude != None)
        )
        
        # Optionally filter out addresses that already have markers to prevent exact overlap
        # However, for relocating, maybe we want the property marker underneath? 
        # Actually, simpler to just show ones that DON'T have a marker yet, 
        # because the inspection/violation marker is effectively the property marker too.
        # If user drags inspection marker, it updates address.
        if active_address_ids:
            properties_query = properties_query.filter(Address.id.notin_(active_address_ids))
            
        properties = properties_query.all()
        
        for prop in properties:
             markers.append(MapMarker(
                id=f"property-{prop.id}",
                entity_id=prop.id, # Using address ID as entity ID for properties
                address_id=prop.id,
                type="property",
                lat=prop.latitude,
                lng=prop.longitude,
                status=None,
                address=prop.combadd,
                description="Property Record",
                severity=None,
                assigned_user_id=None
            ))

    return markers
