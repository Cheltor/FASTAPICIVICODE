from __future__ import annotations

import asyncio
import logging
import os
from functools import lru_cache
from typing import Optional, Tuple

from openai import AsyncOpenAI, NotFoundError, OpenAIError

logger = logging.getLogger(__name__)


class OpenAIConfigError(RuntimeError):
    """Raised when the OpenAI assistant configuration is missing or invalid."""


@lru_cache
def _get_openai_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise OpenAIConfigError("Missing OPENAI_API_KEY environment variable.")
    return api_key


@lru_cache
def _get_assistant_id() -> str:
    assistant_id = os.getenv("OPENAI_ASSISTANT_ID")
    if not assistant_id:
        raise OpenAIConfigError("Missing OPENAI_ASSISTANT_ID environment variable.")
    return assistant_id


_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=_get_openai_api_key())
    return _client


async def _resolve_thread(existing_thread_id: Optional[str]) -> str:
    client = _get_client()

    if existing_thread_id:
            normalized = existing_thread_id.strip()
            if not normalized.startswith("thread_"):
                logger.warning(
                    "Discarding malformed assistant thread id '%s'; expecting prefix 'thread_'.",
                    existing_thread_id,
                )
            else:
                try:
                    await client.beta.threads.retrieve(thread_id=normalized)
                    return normalized
                except NotFoundError:
                    logger.warning(
                        "Assistant thread '%s' was not found; creating a new thread.",
                        normalized,
                    )

    thread_obj = await client.beta.threads.create()
    thread_id = thread_obj.id
    logger.debug("Created new assistant thread %s", thread_id)
    return thread_id


async def _poll_run(thread_id: str, run_id: str, *, poll_interval: float, timeout: float) -> None:
    client = _get_client()
    elapsed = 0.0

    while True:
        run = await client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
        status = getattr(run, "status", "unknown")

        if status == "completed":
            return

        if status in {"failed", "cancelled", "expired"}:
            raise RuntimeError(f"Assistant run did not complete successfully (status={status}).")

        if status == "requires_action":
            raise RuntimeError("Assistant run requires additional action that is not supported by this API integration.")

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        if timeout and elapsed >= timeout:
            raise TimeoutError("Timed out waiting for assistant response.")


async def run_assistant(
    message: str,
    thread_id: Optional[str] = None,
    codes: list = None,
    *,
    poll_interval: float = 0.75,
    timeout: float = 30.0,
) -> Tuple[str, str]:
    """Send a user message to the configured OpenAI assistant and return the reply.
    Args:
        message: The user's message.
        thread_id: Optional existing thread identifier. A new thread is created if omitted.
        codes: A list of relevant code objects to include in the prompt.
        poll_interval: Seconds between status polls for the run.
        timeout: Maximum seconds to wait for completion (0 disables timeout).
    Returns:
        A tuple of (assistant_reply, thread_id).
    """

    if not message or not message.strip():
        raise ValueError("Message must not be empty.")

    client = _get_client()
    assistant_id = _get_assistant_id()

    try:
        thread = await _resolve_thread(thread_id)

        # Prepare the content with code references if available
        content = message
        if codes:
            code_references = "\n\nHere are some relevant code sections:\n"
            for code in codes:
                code_references += f"- **[{code.chapter}.{code.section} - {code.name}]**\n"
            content += code_references

        await client.beta.threads.messages.create(
            thread_id=thread,
            role="user",
            content=content,
        )

        # Include instructions for the assistant in the run
        instructions = (
            "Please answer the user's question. If relevant, use the provided code sections "
            "and cite them in your response using the format `[chapter.section - name]`."
            "If you cannot find a relevant code section, please state that you couldn't find any."
        )

        run = await client.beta.threads.runs.create(
            thread_id=thread,
            assistant_id=assistant_id,
            instructions=instructions,
        )

        await _poll_run(thread, run.id, poll_interval=poll_interval, timeout=timeout)

        messages = await client.beta.threads.messages.list(thread_id=thread, order="desc", limit=10)
        for message_obj in messages.data:
            if message_obj.role != "assistant":
                continue

            for part in getattr(message_obj, "content", []) or []:
                if getattr(part, "type", None) == "text":
                    text = getattr(getattr(part, "text", None), "value", None)
                    if text:
                        return text, thread

        raise RuntimeError("Assistant returned no text response.")

    except OpenAIError as exc:  # pragma: no cover - network failure path
        logger.exception("OpenAI API error")
        raise RuntimeError("OpenAI API error") from exc