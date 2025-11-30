from __future__ import annotations

import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import AliasChoices, BaseModel, Field

from genai_client import GeminiConfigError, run_assistant
from .auth import get_current_user
from models import User
from sqlalchemy.orm import Session
from database import get_db
from database import get_db
from models import ChatLog, AppSetting, ImageAnalysisLog, ActiveStorageBlob, ActiveStorageAttachment
import models

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Assistant"])


class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=6000)
    thread_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("thread_id", "threadId"),
        serialization_alias="threadId",
    )


class AssistantChatResponse(BaseModel):
    reply: str
    thread_id: str = Field(serialization_alias="threadId")


@router.post("/assistant/chat", response_model=AssistantChatResponse)
async def create_assistant_chat(payload: AssistantChatRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AssistantChatResponse:
    """
    Proxy user messages to the configured AI assistant.

    Args:
        payload (AssistantChatRequest): User message and thread ID.
        current_user (User): The authenticated user.
        db (Session): The database session.

    Returns:
        AssistantChatResponse: The assistant's reply and thread ID.

    Raises:
        HTTPException: If configuration missing, timeout, or upstream error.
    """
    try:
        reply, thread_id = await run_assistant(payload.message, payload.thread_id, db)
    except GeminiConfigError as exc:
        logger.error("Gemini configuration error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chat assistant is not configured.",
        ) from exc
    except TimeoutError as exc:
        logger.exception("Timed out waiting for assistant response")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timed out waiting for assistant response.",
        ) from exc
    except Exception as exc:
        logger.exception("Error communicating with assistant")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Error communicating with assistant.",
        ) from exc

    # Persist chat log
    try:
        log = ChatLog(
            user_id=current_user.id,
            thread_id=thread_id,
            user_message=payload.message,
            assistant_reply=reply,
        )
        db.add(log)
        db.commit()
    except Exception:
        # Don't fail the request if logging fails, but record a debug message
        logger.exception('Failed to persist chat log')

    return AssistantChatResponse(reply=reply, thread_id=thread_id)


from fastapi import UploadFile, File
from genai_client import evaluate_image_for_violation
import json

@router.post("/assistant/evaluate-image")
async def evaluate_image(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Evaluate uploaded images for potential code violations.

    Args:
        files (list[UploadFile]): List of image files.
        db (Session): The database session.
        current_user (User): The authenticated user.

    Returns:
        dict: The analysis result (JSON).

    Raises:
        HTTPException: If disabled, invalid images, or analysis fails.
    """
    # Check if enabled
    setting = db.query(models.AppSetting).filter(models.AppSetting.key == "image_analysis_enabled").first()
    if setting and setting.value.lower() == "false":
        raise HTTPException(status_code=503, detail="Image analysis is currently disabled by administrator.")

    images_data = []
    for file in files:
        if not file.content_type.startswith("image/"):
            continue # Skip non-image files or raise error
        
        content = await file.read()
        images_data.append((content, file.content_type, file.filename)) # Added filename
    
    if not images_data:
        raise HTTPException(status_code=400, detail="No valid images provided.")

    # Prepare for logging
    log_entry = models.ImageAnalysisLog(
        user_id=current_user.id,
        image_count=len(images_data),
        status="processing"
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    # Upload images to storage and link to log immediately
    import storage
    from image_utils import normalize_image_for_web
    import uuid
    from datetime import datetime

    # Ensure storage initialized
    storage.ensure_initialized()

    for content, mime_type, filename in images_data:
        try:
            # Re-use normalization logic if possible, or just upload raw if preferred. 
            # Using normalize_image_for_web is safer for consistency.
            normalized_bytes, norm_filename, norm_ct = normalize_image_for_web(content, filename, mime_type)
            
            blob_key = f"image-analysis-logs/{log_entry.id}/{uuid.uuid4()}-{norm_filename}"
            blob_client = storage.blob_service_client.get_blob_client(container=storage.CONTAINER_NAME, blob=blob_key)
            blob_client.upload_blob(normalized_bytes, overwrite=True, content_type=norm_ct)

            blob_row = models.ActiveStorageBlob(
                key=blob_key,
                filename=norm_filename,
                content_type=norm_ct,
                service_name="azure",
                byte_size=len(normalized_bytes),
                created_at=datetime.utcnow(),
            )
            db.add(blob_row)
            db.commit()
            db.refresh(blob_row)

            attachment_row = models.ActiveStorageAttachment(
                name="image",
                record_type="ImageAnalysisLog",
                record_id=log_entry.id,
                blob_id=blob_row.id,
                created_at=datetime.utcnow(),
            )
            db.add(attachment_row)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to upload analysis image log: {e}")
            # Don't fail the request, just log the error

    try:
        # Pass only content and mime_type to the analysis function
        analysis_data = [(d[0], d[1]) for d in images_data]
        result_json_str = await evaluate_image_for_violation(analysis_data, db)
        
        # Update log with success
        log_entry.result = result_json_str
        log_entry.status = "success"
        db.commit()
        
        # Try to parse the JSON to ensure it's valid, otherwise return as raw text wrapped in a structure
        try:
            # Cleanup markdown code blocks if present
            cleaned_result = result_json_str.strip()
            if cleaned_result.startswith("```json"):
                cleaned_result = cleaned_result[7:]
            if cleaned_result.startswith("```"):
                cleaned_result = cleaned_result[3:]
            if cleaned_result.endswith("```"):
                cleaned_result = cleaned_result[:-3]
            
            data = json.loads(cleaned_result.strip())
            return data
        except json.JSONDecodeError:
            # Fallback if the model didn't return strict JSON
            return {
                "observation": "Analysis completed but format was unstructured.",
                "raw_output": result_json_str,
                "potential_violations": []
            }
            
    except Exception as e:
        logger.exception("Failed to evaluate image")
        log_entry.status = "failure"
        log_entry.result = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))
