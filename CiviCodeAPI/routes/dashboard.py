from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from typing import List, Dict, Optional
from datetime import datetime, date
from models import (
    Violation,
    Inspection,
    Citation,
    Comment,
    ViolationComment,
    InspectionComment,
    CitationComment,
    ContactComment,
    License,
    Permit,
    User,
)
from schemas import (
    ViolationCreate,
    ViolationResponse,
    InspectionCreate,
    InspectionResponse,
    CitationCreate,
    CitationResponse,
    CommentCreate,
    CommentResponse,
    LicenseResponse,
    PermitResponse,
    RecentActivityResponse,
    OasDashboardResponse,
    TimelineItem,
    TimelineResponse,
)
from database import get_db
from utils import get_this_workweek, get_last_workweek

router = APIRouter()

def _build_condition(column, user_ids):
    if not user_ids:
        return None
    if len(user_ids) == 1:
        return column == user_ids[0]
    return column.in_(user_ids)


def _apply_condition(query, condition):
    return query.filter(condition) if condition is not None else query


def _compute_counts(db, user_ids, start_day):
    start_of_this_week, end_of_this_week = get_this_workweek(start_day)
    start_of_last_week, end_of_last_week = get_last_workweek(start_day)

    if not user_ids:
        return {
            "active_violations_count": 0,
            "comments_count": 0,
            "inspections_count": 0,
            "citations_count": 0,
            "inspections_this_workweek_count": 0,
            "inspections_last_workweek_count": 0,
            "violations_this_workweek_count": 0,
            "violations_last_workweek_count": 0,
            "comments_this_workweek_count": 0,
            "comments_last_workweek_count": 0,
        }

    violation_user_condition = _build_condition(Violation.user_id, user_ids)
    inspection_user_condition = _build_condition(Inspection.inspector_id, user_ids)
    citation_user_condition = _build_condition(Citation.user_id, user_ids)
    comment_user_condition = _build_condition(Comment.user_id, user_ids)
    violation_comment_user_condition = _build_condition(ViolationComment.user_id, user_ids)
    inspection_comment_user_condition = _build_condition(InspectionComment.user_id, user_ids)
    citation_comment_user_condition = _build_condition(CitationComment.user_id, user_ids)
    contact_comment_user_condition = _build_condition(ContactComment.user_id, user_ids)

    active_violations_count = _apply_condition(
        db.query(func.count(Violation.id)),
        violation_user_condition,
    ).filter(Violation.status == 0).scalar() or 0

    comments_count = (
        (_apply_condition(db.query(func.count(Comment.id)), comment_user_condition).scalar() or 0)
        + (_apply_condition(db.query(func.count(ViolationComment.id)), violation_comment_user_condition).scalar() or 0)
        + (_apply_condition(db.query(func.count(InspectionComment.id)), inspection_comment_user_condition).scalar() or 0)
        + (_apply_condition(db.query(func.count(CitationComment.id)), citation_comment_user_condition).scalar() or 0)
        + (_apply_condition(db.query(func.count(ContactComment.id)), contact_comment_user_condition).scalar() or 0)
    )

    inspections_count = _apply_condition(
        db.query(func.count(Inspection.id)),
        inspection_user_condition,
    ).scalar() or 0

    citations_count = _apply_condition(
        db.query(func.count(Citation.id)),
        citation_user_condition,
    ).scalar() or 0

    inspections_this_workweek_count = _apply_condition(
        db.query(func.count(Inspection.id)),
        inspection_user_condition,
    ).filter(
        or_(
            func.lower(Inspection.status) == 'completed',
            func.lower(Inspection.status) == 'satisfactory',
        ),
        Inspection.updated_at >= start_of_this_week,
        Inspection.updated_at <= end_of_this_week,
    ).scalar() or 0

    inspections_last_workweek_count = _apply_condition(
        db.query(func.count(Inspection.id)),
        inspection_user_condition,
    ).filter(
        or_(
            func.lower(Inspection.status) == 'completed',
            func.lower(Inspection.status) == 'satisfactory',
        ),
        Inspection.updated_at >= start_of_last_week,
        Inspection.updated_at <= end_of_last_week,
    ).scalar() or 0

    violations_this_workweek_count = _apply_condition(
        db.query(func.count(Violation.id)),
        violation_user_condition,
    ).filter(
        Violation.created_at >= start_of_this_week,
        Violation.created_at <= end_of_this_week,
    ).scalar() or 0

    violations_last_workweek_count = _apply_condition(
        db.query(func.count(Violation.id)),
        violation_user_condition,
    ).filter(
        Violation.created_at >= start_of_last_week,
        Violation.created_at <= end_of_last_week,
    ).scalar() or 0

    comments_this_workweek_count = (
        (_apply_condition(db.query(func.count(Comment.id)), comment_user_condition)
         .filter(Comment.created_at >= start_of_this_week, Comment.created_at <= end_of_this_week)
         .scalar() or 0)
        + (_apply_condition(db.query(func.count(ViolationComment.id)), violation_comment_user_condition)
           .filter(ViolationComment.created_at >= start_of_this_week, ViolationComment.created_at <= end_of_this_week)
           .scalar() or 0)
        + (_apply_condition(db.query(func.count(InspectionComment.id)), inspection_comment_user_condition)
           .filter(InspectionComment.created_at >= start_of_this_week, InspectionComment.created_at <= end_of_this_week)
           .scalar() or 0)
        + (_apply_condition(db.query(func.count(CitationComment.id)), citation_comment_user_condition)
           .filter(CitationComment.created_at >= start_of_this_week, CitationComment.created_at <= end_of_this_week)
           .scalar() or 0)
        + (_apply_condition(db.query(func.count(ContactComment.id)), contact_comment_user_condition)
           .filter(ContactComment.created_at >= start_of_this_week, ContactComment.created_at <= end_of_this_week)
           .scalar() or 0)
    )

    comments_last_workweek_count = (
        (_apply_condition(db.query(func.count(Comment.id)), comment_user_condition)
         .filter(Comment.created_at >= start_of_last_week, Comment.created_at <= end_of_last_week)
         .scalar() or 0)
        + (_apply_condition(db.query(func.count(ViolationComment.id)), violation_comment_user_condition)
           .filter(ViolationComment.created_at >= start_of_last_week, ViolationComment.created_at <= end_of_last_week)
           .scalar() or 0)
        + (_apply_condition(db.query(func.count(InspectionComment.id)), inspection_comment_user_condition)
           .filter(InspectionComment.created_at >= start_of_last_week, InspectionComment.created_at <= end_of_last_week)
           .scalar() or 0)
        + (_apply_condition(db.query(func.count(CitationComment.id)), citation_comment_user_condition)
           .filter(CitationComment.created_at >= start_of_last_week, CitationComment.created_at <= end_of_last_week)
           .scalar() or 0)
        + (_apply_condition(db.query(func.count(ContactComment.id)), contact_comment_user_condition)
           .filter(ContactComment.created_at >= start_of_last_week, ContactComment.created_at <= end_of_last_week)
           .scalar() or 0)
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


@router.get("/counts/{user_id}", response_model=Dict[str, int])
def get_counts(
    user_id: int,
    start_day: str = Query('mon', description="Week start day: mon|sun|sat"),
    db: Session = Depends(get_db)
):
    return _compute_counts(db, [user_id], start_day)


@router.get("/counts", response_model=Dict[str, int])
def get_counts_for_role(
    role: int = Query(..., description="Aggregate counts for this user role (e.g., 1 for ONS)"),
    start_day: str = Query('mon', description="Week start day: mon|sun|sat"),
    db: Session = Depends(get_db)
):
    user_ids = [user.id for user in db.query(User).filter(User.role == role).all()]
    return _compute_counts(db, user_ids, start_day)


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


@router.get("/dash/recent", response_model=RecentActivityResponse)
def get_recent_activity(limit: int = Query(5, ge=1, le=50), db: Session = Depends(get_db)):
    size = max(1, min(limit, 50))

    comments = (
        db.query(Comment)
        .options(
            joinedload(Comment.user),
            joinedload(Comment.address),
            joinedload(Comment.unit),
        )
        .order_by(Comment.created_at.desc())
        .limit(size)
        .all()
    )

    inspections = (
        db.query(Inspection)
        .options(joinedload(Inspection.address))
        .filter(Inspection.source != 'Complaint')
        .order_by(Inspection.created_at.desc())
        .limit(size)
        .all()
    )

    complaints = (
        db.query(Inspection)
        .options(joinedload(Inspection.address))
        .filter(Inspection.source == 'Complaint')
        .order_by(Inspection.created_at.desc())
        .limit(size)
        .all()
    )

    licenses = (
        db.query(License)
        .options(joinedload(License.inspection).joinedload(Inspection.address))
        .order_by(License.created_at.desc())
        .limit(size)
        .all()
    )

    violations = (
        db.query(Violation)
        .options(joinedload(Violation.address))
        .order_by(Violation.created_at.desc())
        .limit(size)
        .all()
    )

    permits = (
        db.query(Permit)
        .options(joinedload(Permit.inspection).joinedload(Inspection.address))
        .order_by(Permit.created_at.desc())
        .limit(size)
        .all()
    )

    license_items = []
    for item in licenses:
        address = item.inspection.address if item.inspection and item.inspection.address else None
        license_items.append(
            LicenseResponse(
                id=item.id,
                inspection_id=item.inspection_id,
                sent=item.sent,
                paid=item.paid,
                license_type=item.license_type,
                business_id=item.business_id,
                date_issued=item.date_issued,
                expiration_date=item.expiration_date,
                fiscal_year=item.fiscal_year,
                license_number=item.license_number,
                conditions=item.conditions,
                revoked=item.revoked,
                created_at=item.created_at,
                updated_at=item.updated_at,
                address_id=address.id if address else None,
                combadd=address.combadd if address else None,
            )
        )

    permit_items = []
    for item in permits:
        address = item.inspection.address if item.inspection and item.inspection.address else None
        permit_items.append(
            PermitResponse(
                id=item.id,
                inspection_id=item.inspection_id,
                permit_type=item.permit_type,
                business_id=item.business_id,
                permit_number=item.permit_number,
                date_issued=item.date_issued,
                expiration_date=item.expiration_date,
                conditions=item.conditions,
                paid=item.paid,
                created_at=item.created_at,
                updated_at=item.updated_at,
                address_id=address.id if address else None,
                combadd=address.combadd if address else None,
            )
        )

    violation_items = []
    for item in violations:
        base = ViolationResponse.from_orm(item)
        data = base.dict()
        data['combadd'] = item.address.combadd if item.address else None
        data['address_id'] = item.address_id
        data['deadline_date'] = getattr(item, 'deadline_date', None)
        violation_items.append(data)

    return RecentActivityResponse(
        violations=violation_items,
        comments=comments,
        inspections=inspections,
        complaints=complaints,
        licenses=license_items,
        permits=permit_items,
    )



@router.get("/dash/oas/overview", response_model=OasDashboardResponse)
def get_oas_dashboard_overview(db: Session = Depends(get_db)):
    PAGE_LIMIT = 10
    closed_statuses = {"satisfactory", "no violation found", "closed", "completed", "resolved"}
    status_lower = func.lower(Inspection.status)

    complaint_records = (
        db.query(Inspection)
        .options(joinedload(Inspection.address))
        .filter(func.lower(Inspection.source) == "complaint")
        .filter(
            or_(
                Inspection.status.is_(None),
                status_lower.notin_(tuple(closed_statuses)),
            )
        )
        .order_by(Inspection.created_at.desc())
        .limit(PAGE_LIMIT)
        .all()
    )

    pending_complaints = [InspectionResponse.from_orm(record) for record in complaint_records]

    violation_records = (
        db.query(Violation)
        .options(joinedload(Violation.address))
        .filter(Violation.status == 0)
        .order_by(Violation.updated_at.desc())
        .limit(PAGE_LIMIT)
        .all()
    )

    # Compute the total count of active violations (unlimited) so the UI can show the full number
    active_violations_count = (
        db.query(func.count(Violation.id)).filter(Violation.status == 0).scalar() or 0
    )

    active_violations: List[ViolationResponse] = []
    for violation in violation_records:
        violation_model = ViolationResponse.from_orm(violation)
        violation_model.combadd = violation.address.combadd if violation.address else None
        violation_model.deadline_date = getattr(violation, "deadline_date", None)
        active_violations.append(violation_model)

    base_license_query = (
        db.query(License)
        .options(joinedload(License.inspection).joinedload(Inspection.address))
        .order_by(License.created_at.desc())
    )

    licenses_needing_payment = (
        base_license_query
        .filter(or_(License.paid.is_(False), License.paid.is_(None)))
        .limit(PAGE_LIMIT)
        .all()
    )

    licenses_needing_sending = (
        base_license_query
        .filter(or_(License.sent.is_(False), License.sent.is_(None)))
        .limit(PAGE_LIMIT)
        .all()
    )

    # Compute total number of licenses that need action (either unpaid or not sent)
    licenses_needing_action_count = (
        db.query(func.count(License.id)).filter(
            or_(License.paid.is_(False), License.paid.is_(None), License.sent.is_(False), License.sent.is_(None))
        ).scalar() or 0
    )

    def to_license_response(records: List[License]) -> List[LicenseResponse]:
        items: List[LicenseResponse] = []
        for record in records:
            address = record.inspection.address if record.inspection and record.inspection.address else None
            items.append(
                LicenseResponse(
                    id=record.id,
                    inspection_id=record.inspection_id,
                    sent=record.sent,
                    paid=record.paid,
                    license_type=record.license_type,
                    business_id=record.business_id,
                    date_issued=record.date_issued,
                    expiration_date=record.expiration_date,
                    fiscal_year=record.fiscal_year,
                    license_number=record.license_number,
                    conditions=record.conditions,
                    revoked=record.revoked,
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                    address_id=address.id if address else None,
                    combadd=address.combadd if address else None,
                )
            )
        return items

    return OasDashboardResponse(
        pending_complaints=pending_complaints,
        active_violations=active_violations,
        active_violations_count=active_violations_count,
        licenses_needing_action_count=licenses_needing_action_count,
        licenses_not_paid=to_license_response(licenses_needing_payment),
        licenses_not_sent=to_license_response(licenses_needing_sending),
    )

# Get all inspections for a user where the status is not 2 (completed)
@router.get("/dash/inspections/{user_id}", response_model=List[InspectionResponse])
def get_inspections(user_id: int, db: Session = Depends(get_db)):
    inspections = db.query(Inspection).filter(Inspection.inspector_id == user_id, Inspection.status.is_(None)).all()
    return inspections






@router.get("/dash/reporting", response_model=Dict)
def get_reporting_metrics(db: Session = Depends(get_db)):
    # 1. Case Aging Metrics (Open Violations)
    # Buckets: <30, 30-60, 60-90, 90+
    now = datetime.utcnow()
    open_violations = db.query(Violation).filter(Violation.status == 0).all()
    
    aging_buckets = {
        "<30 Days": 0,
        "30-60 Days": 0,
        "60-90 Days": 0,
        "90+ Days": 0
    }
    total_age_days = 0
    count = 0

    for v in open_violations:
        age = (now - v.created_at).days
        total_age_days += age
        count += 1
        if age < 30:
            aging_buckets["<30 Days"] += 1
        elif age < 60:
            aging_buckets["30-60 Days"] += 1
        elif age < 90:
            aging_buckets["60-90 Days"] += 1
        else:
            aging_buckets["90+ Days"] += 1

    avg_age = round(total_age_days / count, 1) if count > 0 else 0

    # 2. Rental License Compliance
    # Statuses: Valid (paid & not expired), Expired (expired), Unpaid (not paid), Revoked (revoked)
    # Note: Logic priority -> Revoked > Expired > Unpaid > Valid
    licenses = db.query(License).all()
    compliance_counts = {
        "Valid": 0,
        "Expired": 0,
        "Unpaid": 0,
        "Revoked": 0
    }
    
    today = date.today()

    for lic in licenses:
        if lic.revoked:
            compliance_counts["Revoked"] += 1
        elif lic.expiration_date and lic.expiration_date < today:
            compliance_counts["Expired"] += 1
        elif not lic.paid:
            compliance_counts["Unpaid"] += 1
        else:
            compliance_counts["Valid"] += 1

    # 3. Time to Close Metrics (Closed Violations)
    closed_violations = db.query(Violation).filter(Violation.status == 1, Violation.closed_at.isnot(None)).all()
    total_close_days = 0
    closed_count = 0
    
    for v in closed_violations:
        days_to_close = (v.closed_at - v.created_at).days
        # Ensure non-negative (in case of clock skew or data issues)
        if days_to_close < 0: days_to_close = 0
        total_close_days += days_to_close
        closed_count += 1
        
    avg_time_to_close = round(total_close_days / closed_count, 1) if closed_count > 0 else 0

    return {
        "case_aging_buckets": aging_buckets,
        "average_case_age_days": avg_age,
        "open_violation_count": count,
        "rental_license_compliance": compliance_counts,
        "total_license_count": len(licenses),
        "average_time_to_close_days": avg_time_to_close,
        "closed_violation_count": closed_count,
    }


@router.get("/dash/timeline", response_model=TimelineResponse)
def get_timeline(
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[datetime] = Query(None),
    db: Session = Depends(get_db)
):
    # If no cursor, use current time
    if not cursor:
        cursor = datetime.utcnow()

    # Helper to apply cursor and limit
    def apply_pagination(query, model_class):
        return (
            query.filter(model_class.created_at < cursor)
            .order_by(model_class.created_at.desc())
            .limit(limit)
        )

    # 1. Comments
    comments = apply_pagination(
        db.query(Comment).options(joinedload(Comment.user), joinedload(Comment.address)),
        Comment
    ).all()

    # 2. Inspections (excluding complaints for now, or include them?)
    # Let's include all inspections
    inspections = apply_pagination(
        db.query(Inspection).options(joinedload(Inspection.inspector), joinedload(Inspection.address)),
        Inspection
    ).all()

    # 3. Violations
    violations = apply_pagination(
        db.query(Violation).options(joinedload(Violation.user), joinedload(Violation.address)),
        Violation
    ).all()

    # 4. Citations
    citations = apply_pagination(
        db.query(Citation).options(joinedload(Citation.user), joinedload(Citation.violation).joinedload(Violation.address)),
        Citation
    ).all()

    # 5. Licenses
    licenses = apply_pagination(
        db.query(License).options(joinedload(License.inspection).joinedload(Inspection.address)),
        License
    ).all()

    # 6. Permits
    permits = apply_pagination(
        db.query(Permit).options(joinedload(Permit.inspection).joinedload(Inspection.address)),
        Permit
    ).all()

    # Combine and sort
    all_items = []

    # Helper to create TimelineItem
    def create_item(type_name, obj, description, created_at, user=None, address=None, entity_link=None, metadata=None):
        return TimelineItem(
            id=obj.id,
            type=type_name,
            description=description,
            created_at=created_at,
            user=user,
            address_id=address.id if address else None,
            combadd=address.combadd if address else None,
            entity_id=obj.id,
            entity_link=entity_link,
            metadata=metadata
        )

    for c in comments:
        desc = f"commented on {c.address.combadd if c.address else 'an address'}"
        all_items.append(create_item('comment', c, desc, c.created_at, c.user, c.address, f"/admin/comments/{c.id}/edit"))

    for i in inspections:
        user = i.inspector
        desc = f"performed {i.source} inspection"
        all_items.append(create_item('inspection', i, desc, i.created_at, user, i.address, f"/inspection/{i.id}", {"status": i.status}))

    for v in violations:
        desc = f"recorded a violation: {v.violation_type or 'Unknown'}"
        all_items.append(create_item('violation', v, desc, v.created_at, v.user, v.address, f"/violation/{v.id}", {"status": v.status}))

    for c in citations:
        # Citations might not have a direct user relationship in the model def above, let's check
        # The model has user_id and user relationship.
        desc = f"issued a citation (${c.fine})"
        address = c.violation.address if c.violation else None
        all_items.append(create_item('citation', c, desc, c.created_at, c.user, address, f"/citation/{c.id}", {"fine": c.fine}))

    for l in licenses:
        # Licenses don't have a direct 'user' who created them usually, it's system or via inspection
        # We might skip user for licenses or use the inspector
        user = l.inspection.inspector if l.inspection else None
        address = l.inspection.address if l.inspection else None
        desc = f"issued license #{l.license_number}"
        all_items.append(create_item('license', l, desc, l.created_at, user, address, f"/license/{l.id}", {"type": l.license_type}))

    for p in permits:
        user = p.inspection.inspector if p.inspection else None
        address = p.inspection.address if p.inspection else None
        desc = f"issued permit #{p.permit_number}"
        all_items.append(create_item('permit', p, desc, p.created_at, user, address, f"/permit/{p.id}", {"type": p.permit_type}))

    # Sort descending
    all_items.sort(key=lambda x: x.created_at, reverse=True)

    # Take top 'limit'
    final_items = all_items[:limit]

    # Determine next cursor
    next_cursor = None
    if final_items:
        next_cursor = final_items[-1].created_at

    return TimelineResponse(items=final_items, next_cursor=next_cursor)
