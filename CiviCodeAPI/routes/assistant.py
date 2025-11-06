from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import AliasChoices, BaseModel, Field

from CiviCodeAPI.genai_client import OpenAIConfigError, run_assistant
from .auth import get_current_user
from CiviCodeAPI.models import User
from sqlalchemy.orm import Session
from CiviCodeAPI.database import get_db
from CiviCodeAPI.models import ChatLog

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


@router.post("/chat", response_model=AssistantChatResponse)
async def create_assistant_chat(payload: AssistantChatRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AssistantChatResponse:
    """Proxy user messages to the configured OpenAI assistant."""
    try:
        reply, thread_id = await run_assistant(payload.message, payload.thread_id)
    except OpenAIConfigError as exc:
        logger.error("OpenAI configuration error: %s", exc)
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
