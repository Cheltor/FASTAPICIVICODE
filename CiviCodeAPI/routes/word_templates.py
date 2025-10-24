from fastapi import APIRouter, HTTPException, Response, Depends
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models import Violation
from docxtpl import DocxTemplate
from io import BytesIO
import os
from datetime import date

router = APIRouter()

@router.get("/violation/{violation_id}/notice")
def generate_violation_notice(violation_id: int, db: Session = Depends(get_db)):
    violation = (
        db.query(Violation)
        .filter(Violation.id == violation_id)
        .options(
            joinedload(Violation.address),
            joinedload(Violation.codes),
            joinedload(Violation.user)
        )
        .first()
    )
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")

    # Prepare context for the template
    context = {
        "today": date.today().strftime("%m/%d/%Y"),
        "combadd": violation.address.combadd if violation.address else "",
        "premisezip": violation.address.premisezip if violation.address else "",
        "ownername": violation.address.ownername if violation.address else "",
        "owneraddress": violation.address.owneraddress if violation.address else "",
        "ownercity": violation.address.ownercity if violation.address else "",
        "ownerstate": violation.address.ownerstate if violation.address else "",
        "ownerzip": violation.address.ownerzip if violation.address else "",
        "created_at": violation.created_at.strftime("%m/%d/%Y") if violation.created_at else "",
        "deadline_date": violation.deadline_date.strftime("%m/%d/%Y") if violation.deadline_date else "",
        "userphone": violation.user.phone if violation.user and violation.user.phone else "",
        "username": violation.user.name if violation.user and violation.user.name else "",
        "violation_codes": [
            {
                "chapter": c.chapter,
                "section": c.section,
                "name": c.name,
                "description": c.description,
            } for c in violation.codes
        ] if violation.codes else [],
    }

    template_path = os.path.join(os.path.dirname(__file__), "../templates/violation_notice_template.docx")
    doc = DocxTemplate(template_path)
    doc.render(context)

    file_stream = BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)

    headers = {
        'Content-Disposition': f'attachment; filename="violation_notice_{violation_id}.docx"'
    }
    return Response(content=file_stream.read(), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers=headers)


@router.get("/violation/{violation_id}/compliance-letter")
def generate_compliance_letter(violation_id: int, db: Session = Depends(get_db)):
    violation = (
        db.query(Violation)
        .filter(Violation.id == violation_id)
        .options(
            joinedload(Violation.address),
            joinedload(Violation.codes),
            joinedload(Violation.user)
        )
        .first()
    )
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")

    address = violation.address
    today_str = date.today().strftime("%B %d, %Y")
    created_at = violation.created_at.strftime("%B %d, %Y") if violation.created_at else ""
    resolved_at = violation.updated_at.strftime("%B %d, %Y") if violation.updated_at else today_str

    owner_name = address.ownername if address and address.ownername else "Property Owner"
    owner_address_line1 = address.owneraddress if address and address.owneraddress else ""
    owner_city = address.ownercity if address and address.ownercity else ""
    owner_state = address.ownerstate if address and address.ownerstate else ""
    owner_zip = address.ownerzip if address and address.ownerzip else ""
    property_reference = address.combadd if address and address.combadd else ""

    codes_context = [
        {
            "chapter": code.chapter,
            "section": code.section,
            "name": code.name,
            "description": code.description,
        }
        for code in (violation.codes or [])
    ]

    context = {
        "today": today_str,
        "combadd": property_reference,
        "ownername": owner_name,
        "owneraddress": owner_address_line1,
        "ownercity": owner_city,
        "ownerstate": owner_state,
        "ownerzip": owner_zip,
        "created_at": created_at,
        "username": (violation.user.name if violation.user and violation.user.name else violation.user.email if violation.user else ""),
        "userphone": (violation.user.phone if violation.user and violation.user.phone else ""),
        "violation_codes": codes_context,
    }

    template_path = os.path.join(os.path.dirname(__file__), "../templates/compliance_notice_template.docx")
    doc = DocxTemplate(template_path)
    doc.render(context)

    file_stream = BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)

    headers = {
        'Content-Disposition': f'attachment; filename="compliance_letter_{violation_id}.docx"'
    }
    return Response(
        content=file_stream.read(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers
    )
