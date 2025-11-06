from fastapi import APIRouter, HTTPException, Response, Depends
from sqlalchemy.orm import Session, joinedload
from CiviCodeAPI.database import get_db
from CiviCodeAPI.models import Violation, License, Inspection, Business
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


@router.get("/license/{license_id}/download")
def generate_license_document(license_id: int, db: Session = Depends(get_db)):
    lic = (
        db.query(License)
        .filter(License.id == license_id)
        .options(joinedload(License.inspection).joinedload(Inspection.address))
        .first()
    )
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")

    inspection = lic.inspection
    address = inspection.address if inspection else None

    business = None
    if getattr(lic, 'business_id', None):
        try:
            business = db.query(Business).filter(Business.id == lic.business_id).first()
        except Exception:
            business = None

    # Map license types to template files
    template_map = {
        1: "FY26 Business License Template.docx",
        2: "FY26 Conditional SFR License .docx",
        3: "FY26 Multi Family License Template.docx",
    }
    tpl_filename = template_map.get(lic.license_type, "FY26 Business License Template.docx")

    # Build context - include common fields expected by templates
    context = {
        "today": date.today().strftime("%m/%d/%Y"),
        "license_number": lic.license_number or "",
        "date_issued": lic.date_issued.strftime("%m/%d/%Y") if lic.date_issued else "",
        "expiration_date": lic.expiration_date.strftime("%m/%d/%Y") if lic.expiration_date else "",
        "fiscal_year": lic.fiscal_year or "",
        "conditions": lic.conditions or "",
        # inspection/address fields
        "combadd": address.combadd if address and getattr(address, 'combadd', None) else "",
        "premisezip": address.premisezip if address and getattr(address, 'premisezip', None) else "",
        "ownername": address.ownername if address and getattr(address, 'ownername', None) else "",
        "owneraddress": address.owneraddress if address and getattr(address, 'owneraddress', None) else "",
        "ownercity": address.ownercity if address and getattr(address, 'ownercity', None) else "",
        "ownerstate": address.ownerstate if address and getattr(address, 'ownerstate', None) else "",
        "ownerzip": address.ownerzip if address and getattr(address, 'ownerzip', None) else "",
        # business fields
        "business_name": business.name if business and getattr(business, 'name', None) else "",
        "business_address": getattr(business, 'address', '') if business else "",
    }

    template_path = os.path.join(os.path.dirname(__file__), "../templates", tpl_filename)
    if not os.path.exists(template_path):
        raise HTTPException(status_code=500, detail=f"Template not found: {tpl_filename}")

    doc = DocxTemplate(template_path)
    doc.render(context)

    file_stream = BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)

    # Build a safe filename for download
    def _sanitize(s):
        return ''.join([c if c.isalnum() else '_' for c in (s or '')]).strip('_') or f'license_{license_id}'

    primary_label = business.name if business and business.name else (address.combadd if address and getattr(address, 'combadd', None) else f'license_{license_id}')
    safe = _sanitize(primary_label)

    headers = {
        'Content-Disposition': f'attachment; filename="{safe}_license_{license_id}.docx"'
    }
    return Response(
        content=file_stream.read(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )
