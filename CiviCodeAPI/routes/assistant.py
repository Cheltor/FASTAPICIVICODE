from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import AliasChoices, BaseModel, Field

from genai_client import OpenAIConfigError, run_assistant

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
async def create_assistant_chat(payload: AssistantChatRequest) -> AssistantChatResponse:
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

    return AssistantChatResponse(reply=reply, thread_id=thread_id)
