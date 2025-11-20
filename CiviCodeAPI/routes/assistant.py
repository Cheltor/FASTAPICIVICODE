from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import AliasChoices, BaseModel, Field

from genai_client import GeminiConfigError, run_assistant
from .auth import get_current_user
from models import User
from sqlalchemy.orm import Session
from database import get_db
from models import ChatLog

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
    """Proxy user messages to the configured AI assistant."""
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
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Evaluate an uploaded image for potential code violations.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")
        
    try:
        content = await file.read()
        result_json_str = await evaluate_image_for_violation(content, file.content_type, db)
        
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
        raise HTTPException(status_code=500, detail=str(e))
