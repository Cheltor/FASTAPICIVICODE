from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from typing import List, Dict
from models import (
    Violation,
    Inspection,
    Citation,
    Comment,
    ViolationComment,
    InspectionComment,
    CitationComment,
    ContactComment,
)
from schemas import ViolationCreate, ViolationResponse, InspectionCreate, InspectionResponse, CitationCreate, CitationResponse, CommentCreate, CommentResponse
from database import get_db
from utils import get_this_workweek, get_last_workweek

router = APIRouter()

@router.get("/counts/{user_id}", response_model=Dict[str, int])
def get_counts(
    user_id: int,
    start_day: str = Query('mon', description="Week start day: mon|sun|sat"),
    db: Session = Depends(get_db)
):
    start_of_this_week, end_of_this_week = get_this_workweek(start_day)
    start_of_last_week, end_of_last_week = get_last_workweek(start_day)

    active_violations_count = db.query(func.count(Violation.id)).filter(Violation.user_id == user_id, Violation.status == 0).scalar()
    # Sum comments across all comment-bearing tables for this user (all time)
    comments_count = (
        (db.query(func.count(Comment.id)).filter(Comment.user_id == user_id).scalar() or 0)
        + (db.query(func.count(ViolationComment.id)).filter(ViolationComment.user_id == user_id).scalar() or 0)
        + (db.query(func.count(InspectionComment.id)).filter(InspectionComment.user_id == user_id).scalar() or 0)
        + (db.query(func.count(CitationComment.id)).filter(CitationComment.user_id == user_id).scalar() or 0)
        + (db.query(func.count(ContactComment.id)).filter(ContactComment.user_id == user_id).scalar() or 0)
    )
    inspections_count = db.query(func.count(Inspection.id)).filter(Inspection.inspector_id == user_id).scalar()
    citations_count = db.query(func.count(Citation.id)).filter(Citation.user_id == user_id).scalar()

    # Inspections counted when marked completed within the week window by this inspector
    inspections_this_workweek_count = (
        db.query(func.count(Inspection.id))
        .filter(
            Inspection.inspector_id == user_id,
            # Treat variations of completed; also allow 'Satisfactory' as completed
            or_(
                func.lower(Inspection.status) == 'completed',
                func.lower(Inspection.status) == 'satisfactory',
            ),
            Inspection.updated_at >= start_of_this_week,
            Inspection.updated_at <= end_of_this_week,
        )
        .scalar()
    )
    inspections_last_workweek_count = (
        db.query(func.count(Inspection.id))
        .filter(
            Inspection.inspector_id == user_id,
            or_(
                func.lower(Inspection.status) == 'completed',
                func.lower(Inspection.status) == 'satisfactory',
            ),
            Inspection.updated_at >= start_of_last_week,
            Inspection.updated_at <= end_of_last_week,
        )
        .scalar()
    )

    # Violations counted by creation date (created by this user)
    violations_this_workweek_count = (
        db.query(func.count(Violation.id))
        .filter(
            Violation.user_id == user_id,
            Violation.created_at >= start_of_this_week,
            Violation.created_at <= end_of_this_week,
        )
        .scalar()
    )
    violations_last_workweek_count = (
        db.query(func.count(Violation.id))
        .filter(
            Violation.user_id == user_id,
            Violation.created_at >= start_of_last_week,
            Violation.created_at <= end_of_last_week,
        )
        .scalar()
    )

    # Comments counted across all comment tables by creation date
    comments_this_workweek_count = (
        (db.query(func.count(Comment.id)).filter(Comment.user_id == user_id, Comment.created_at >= start_of_this_week, Comment.created_at <= end_of_this_week).scalar() or 0)
        + (db.query(func.count(ViolationComment.id)).filter(ViolationComment.user_id == user_id, ViolationComment.created_at >= start_of_this_week, ViolationComment.created_at <= end_of_this_week).scalar() or 0)
        + (db.query(func.count(InspectionComment.id)).filter(InspectionComment.user_id == user_id, InspectionComment.created_at >= start_of_this_week, InspectionComment.created_at <= end_of_this_week).scalar() or 0)
        + (db.query(func.count(CitationComment.id)).filter(CitationComment.user_id == user_id, CitationComment.created_at >= start_of_this_week, CitationComment.created_at <= end_of_this_week).scalar() or 0)
        + (db.query(func.count(ContactComment.id)).filter(ContactComment.user_id == user_id, ContactComment.created_at >= start_of_this_week, ContactComment.created_at <= end_of_this_week).scalar() or 0)
    )
    comments_last_workweek_count = (
        (db.query(func.count(Comment.id)).filter(Comment.user_id == user_id, Comment.created_at >= start_of_last_week, Comment.created_at <= end_of_last_week).scalar() or 0)
        + (db.query(func.count(ViolationComment.id)).filter(ViolationComment.user_id == user_id, ViolationComment.created_at >= start_of_last_week, ViolationComment.created_at <= end_of_last_week).scalar() or 0)
        + (db.query(func.count(InspectionComment.id)).filter(InspectionComment.user_id == user_id, InspectionComment.created_at >= start_of_last_week, InspectionComment.created_at <= end_of_last_week).scalar() or 0)
        + (db.query(func.count(CitationComment.id)).filter(CitationComment.user_id == user_id, CitationComment.created_at >= start_of_last_week, CitationComment.created_at <= end_of_last_week).scalar() or 0)
        + (db.query(func.count(ContactComment.id)).filter(ContactComment.user_id == user_id, ContactComment.created_at >= start_of_last_week, ContactComment.created_at <= end_of_last_week).scalar() or 0)
    )

    return {
        "active_violations_count": active_violations_count,
        "comments_count": comments_count,
        "inspections_count": inspections_count,
        "citations_count": citations_count,
        "inspections_this_workweek_count": inspections_this_workweek_count,
        "inspections_last_workweek_count": inspections_last_workweek_count,
        "violations_this_workweek_count": violations_this_workweek_count,
        "violations_last_workweek_count": violations_last_workweek_count,
        "comments_this_workweek_count": comments_this_workweek_count,
        "comments_last_workweek_count": comments_last_workweek_count,
    }

# Get 10 most recent comments by user
@router.get("/dash/comments/{user_id}", response_model=List[CommentResponse])
def get_recent_comments(user_id: int, db: Session = Depends(get_db)):
    comments = db.query(Comment).filter(Comment.user_id == user_id).order_by(Comment.updated_at.desc()).limit(10).all()
    return comments

# Get all active violations for a user
@router.get("/dash/violations/{user_id}", response_model=List[ViolationResponse])
def get_active_violations(user_id: int, db: Session = Depends(get_db)):
    violations = (
        db.query(Violation)
        .filter(Violation.user_id == user_id, Violation.status == 0)
        .options(joinedload(Violation.address))  # Eagerly load the Address relationship
        .order_by(Violation.updated_at.desc())
        .all()
    )

    # Add combadd to the response
    response = []
    for violation in violations:
        violation_dict = violation.__dict__
        violation_dict['combadd'] = violation.address.combadd if violation.address else None
        violation_dict['deadline_date'] = violation.deadline_date  # Access computed property
        response.append(violation_dict)
    
    return response


# Get all inspections for a user where the status is not 2 (completed)
@router.get("/dash/inspections/{user_id}", response_model=List[InspectionResponse])
def get_inspections(user_id: int, db: Session = Depends(get_db)):
    inspections = db.query(Inspection).filter(Inspection.inspector_id == user_id, Inspection.status.is_(None)).all()
    return inspections




