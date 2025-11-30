from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from models import DocumentTemplate
from utils_templates import validate_template_category
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class TemplateResponse(BaseModel):
    id: int
    name: str
    category: str
    filename: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

@router.post("/templates/", response_model=TemplateResponse)
def upload_template(
    file: UploadFile = File(...),
    name: str = Form(...),
    category: str = Form(...),
    db: Session = Depends(get_db)
):
    if category not in ['violation', 'compliance', 'license']:
        raise HTTPException(status_code=400, detail="Invalid category. Must be 'violation', 'compliance', or 'license'.")

    if not file.filename.endswith('.docx'):
        raise HTTPException(status_code=400, detail="Only .docx files are allowed.")

    content = file.file.read()

    try:
        validate_template_category(content, category)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    new_template = DocumentTemplate(
        name=name,
        category=category,
        filename=file.filename,
        content=content
    )
    db.add(new_template)
    db.commit()
    db.refresh(new_template)
    return new_template

@router.get("/templates/", response_model=List[TemplateResponse])
def list_templates(
    category: Optional[str] = Query(None, regex="^(violation|compliance|license)$"),
    db: Session = Depends(get_db)
):
    query = db.query(DocumentTemplate)
    if category:
        query = query.filter(DocumentTemplate.category == category)
    return query.all()

@router.delete("/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)):
    template = db.query(DocumentTemplate).filter(DocumentTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    db.delete(template)
    db.commit()
    return {"detail": "Template deleted"}

@router.get("/templates/{template_id}/download")
def download_template(template_id: int, db: Session = Depends(get_db)):
    from fastapi.responses import Response
    template = db.query(DocumentTemplate).filter(DocumentTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    headers = {
        'Content-Disposition': f'attachment; filename="{template.filename}"'
    }
    return Response(
        content=template.content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers
    )
