from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from models import DocumentTemplate, User
from utils_templates import validate_template_category
from pydantic import BaseModel
from datetime import datetime
from urllib.parse import quote
from routes.users import read_users_me as get_current_user

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if category not in ['violation', 'compliance', 'license']:
        raise HTTPException(status_code=400, detail="Invalid category. Must be 'violation', 'compliance', or 'license'.")

    if not file.filename.lower().endswith('.docx'):
        raise HTTPException(status_code=400, detail="Only .docx files are allowed.")

    if ".." in file.filename or "/" in file.filename or "\\" in file.filename:
         raise HTTPException(status_code=400, detail="Invalid filename.")

    # Check file size (limit to 10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    content = file.file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds the 10MB limit.")

    try:
        validate_template_category(content)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(DocumentTemplate)
    if category:
        query = query.filter(DocumentTemplate.category == category)
    return query.all()

@router.delete("/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    template = db.query(DocumentTemplate).filter(DocumentTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    db.delete(template)
    db.commit()
    return {"detail": "Template deleted"}

@router.get("/templates/{template_id}/download")
def download_template(template_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    template = db.query(DocumentTemplate).filter(DocumentTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    safe_filename = quote(template.filename, safe='')
    headers = {
        'Content-Disposition': f'attachment; filename="{safe_filename}"'
    }
    return Response(
        content=template.content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers
    )
