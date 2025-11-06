from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, Dict
from datetime import datetime, timedelta, date

from CiviCodeAPI.database import get_db
from CiviCodeAPI.models import Inspection, Violation, Citation

router = APIRouter()


def _parse_dates(start_date: Optional[str], end_date: Optional[str]) -> tuple[datetime, datetime]:
    """Parse YYYY-MM-DD strings to an inclusive [start_of_day, end_of_day] range.
    Defaults to last 14 days when not provided.
    """
    if start_date and end_date:
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0, microsecond=0)
            ed = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, microsecond=999999)
            return sd, ed
        except ValueError:
            pass  # fall through to default

    today = datetime.utcnow()
    ed = today.replace(hour=23, minute=59, second=59, microsecond=999999)
    sd = (today - timedelta(days=14)).replace(hour=0, minute=0, second=0, microsecond=0)
    return sd, ed


def _count_inspection_window(db: Session, start_dt: datetime, end_dt: datetime, *, term: str, contains: bool = False) -> Dict[str, int]:
    """Return counts for inspection request, any updates, and approvals for a type.
    - Request: created_at in range
    - Updated: updated_at in range
    - Approved: status in (completed, satisfactory) and updated_at in range
    Filtering by source either exact match (case-insensitive) or contains term.
    """
    src = func.lower(Inspection.source)
    t = term.lower()
    if contains:
        src_filter = src.like(f"%{t}%")
    else:
        src_filter = (src == t)

    completed = func.lower(Inspection.status).in_(["completed", "satisfactory"])  # treat these as approved

    requests = db.query(func.count(Inspection.id)).filter(
        src_filter,
        Inspection.created_at >= start_dt,
        Inspection.created_at <= end_dt,
    ).scalar() or 0

    updated = db.query(func.count(Inspection.id)).filter(
        src_filter,
        Inspection.updated_at >= start_dt,
        Inspection.updated_at <= end_dt,
    ).scalar() or 0

    approved = db.query(func.count(Inspection.id)).filter(
        src_filter,
        completed,
        Inspection.updated_at >= start_dt,
        Inspection.updated_at <= end_dt,
    ).scalar() or 0

    return {
        "requests": requests,
        "updated": updated,
        "approved": approved,
    }


@router.get("/sir/stats", response_model=Dict[str, int])
def get_sir_stats(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    start_dt, end_dt = _parse_dates(start_date, end_date)

    # Complaints
    complaints_made = db.query(func.count(Inspection.id)).filter(
        func.lower(Inspection.source) == "complaint",
        Inspection.created_at >= start_dt,
        Inspection.created_at <= end_dt,
    ).scalar() or 0

    # Complaint responses: complaints updated within the window with a non-empty status and updated after created
    complaint_responses = db.query(func.count(Inspection.id)).filter(
        func.lower(Inspection.source) == "complaint",
        Inspection.updated_at >= start_dt,
        Inspection.updated_at <= end_dt,
        Inspection.updated_at > Inspection.created_at,
        func.coalesce(func.nullif(func.trim(Inspection.status), ''), None) != None,
    ).scalar() or 0

    # Violations & Warnings (warnings = any violation notice created)
    violations = db.query(func.count(Violation.id)).filter(
        Violation.created_at >= start_dt,
        Violation.created_at <= end_dt,
    ).scalar() or 0

    # Per requirement, "warning" should mean any violation notice created
    warnings = violations

    # Citations
    citations = db.query(func.count(Citation.id)).filter(
        Citation.created_at >= start_dt,
        Citation.created_at <= end_dt,
    ).scalar() or 0

    # License and Permit inspections
    sf = _count_inspection_window(db, start_dt, end_dt, term="Single Family License")
    mf = _count_inspection_window(db, start_dt, end_dt, term="Multifamily License")
    bl = _count_inspection_window(db, start_dt, end_dt, term="Business License")
    permit = _count_inspection_window(db, start_dt, end_dt, term="permit", contains=True)

    return {
        # complaints/violations/citations
        "complaints_made": complaints_made,
        "complaint_responses": complaint_responses,
        "warnings": warnings,
        "violations": violations,
        "citations": citations,

        # single family
        "sf_inspections": sf["requests"],
        "sf_inspection_updated": sf["updated"],
        "sf_inspection_approved": sf["approved"],

        # multifamily
        "mf_inspections": mf["requests"],
        "mf_inspection_updated": mf["updated"],
        "mf_inspection_approved": mf["approved"],

        # business license
        "bl_inspections": bl["requests"],
        "bl_inspection_updated": bl["updated"],
        "bl_inspection_approved": bl["approved"],

        # permit
        "permit_inspections": permit["requests"],
        "permit_inspection_updated": permit["updated"],
        "permit_inspection_approved": permit["approved"],
    }
