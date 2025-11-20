from __future__ import annotations

import logging
import os
import json
from typing import Optional, Tuple, List
from functools import lru_cache

import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
from sqlalchemy.orm import Session
from sqlalchemy import or_

from models import Code, ChatLog

logger = logging.getLogger(__name__)

class GeminiConfigError(RuntimeError):
    """Raised when the Gemini configuration is missing or invalid."""

@lru_cache
def _configure_gemini() -> None:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise GeminiConfigError("Missing GOOGLE_API_KEY environment variable.")
    genai.configure(api_key=api_key)

def search_codes(db: Session, query: str) -> str:
    """
    Search for codes in the database based on a query string.
    
    Args:
        query: The search query to find relevant codes.
        
    Returns:
        A JSON string containing a list of matching codes with their details.
    """
    try:
        # Perform a case-insensitive search on name, description, chapter, or section
        search_filter = or_(
            Code.name.ilike(f"%{query}%"),
            Code.description.ilike(f"%{query}%"),
            Code.chapter.ilike(f"%{query}%"),
            Code.section.ilike(f"%{query}%")
        )
        
        results = db.query(Code).filter(search_filter).limit(5).all()
        
        if not results:
            return "No matching codes found."
            
        codes_data = []
        for code in results:
            codes_data.append({
                "id": code.id,
                "chapter": code.chapter,
                "section": code.section,
                "name": code.name,
                "description": code.description[:200] + "..." if code.description and len(code.description) > 200 else code.description
            })
            
        return json.dumps(codes_data)
    except Exception as e:
        logger.exception("Error searching codes: %s", e)
        return f"Error searching codes: {str(e)}"

def _get_history(db: Session, thread_id: str) -> List[dict]:
    """
    Retrieve chat history for a given thread ID.
    """
    if not thread_id:
        return []
        
    logs = db.query(ChatLog).filter(ChatLog.thread_id == thread_id).order_by(ChatLog.created_at).all()
    
    history = []
    for log in logs:
        history.append({"role": "user", "parts": [log.user_message]})
        if log.assistant_reply:
            history.append({"role": "model", "parts": [log.assistant_reply]})
            
    return history

async def run_assistant(
    message: str,
    thread_id: Optional[str] = None,
    db: Session = None
) -> Tuple[str, str]:
    """
    Send a user message to Gemini and return the reply.
    
    Args:
        message: The user's message.
        thread_id: Optional existing thread identifier.
        db: Database session for tool execution and history retrieval.
        
    Returns:
        A tuple of (assistant_reply, thread_id).
    """
    if not db:
        raise ValueError("Database session is required for Gemini assistant.")

    _configure_gemini()
    
    # Use a consistent thread_id if not provided
    import uuid
    if not thread_id:
        thread_id = f"thread_{uuid.uuid4()}"

    # Define the tool
    # We need to wrap the function to inject the db session, but Gemini tools 
    # expect functions with simple arguments. 
    # A better approach for this stateless tool is to define the tool definition 
    # and handle execution manually or use a wrapper that doesn't expose 'db' to Gemini.
    
    # We will define the tool for Gemini without the 'db' argument in the signature visible to the model
    # but we will call the actual implementation with 'db'.
    
    tools_config = [
        {
            "function_declarations": [
                {
                    "name": "search_codes",
                    "description": "Search for municipal codes/laws based on a query. Use this to find relevant code sections to answer user questions about regulations.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "query": {
                                "type": "STRING",
                                "description": "The search term or phrase to look for in the codes."
                            }
                        },
                        "required": ["query"]
                    }
                }
            ]
        }
    ]

    system_instruction = """You are a helpful assistant for a municipal code enforcement application. 
    Your goal is to help users understand local codes and regulations.
    
    When you answer questions about codes:
    1. ALWAYS use the 'search_codes' tool to find the exact code text.
    
    2. Cite the code using the format: [Code: <id>] (e.g., [Code: 123]). 
       Do NOT use markdown links like [Code 123](...) for the citation itself, just the bracketed format.
       The frontend will automatically turn [Code: <id>] into a clickable link.
    3. Be concise and helpful.
    """

    model = genai.GenerativeModel(
        model_name="gemini-flash-latest",
        tools=tools_config,
        system_instruction=system_instruction
    )

    # Load history
    history = _get_history(db, thread_id)
    
    chat = model.start_chat(history=history)
    
    try:
        response = await chat.send_message_async(message)
        
        # Handle tool calls in a loop to support multi-turn interactions
        while True:
            part = response.candidates[0].content.parts[0]
            
            if not part.function_call:
                break
                
            fc = part.function_call
            if fc.name == "search_codes":
                query = fc.args["query"]
                logger.info(f"Gemini requested search_codes with query: {query}")
                
                # Execute tool
                tool_result = search_codes(db, query)
                
                # Send result back to model
                response = await chat.send_message_async(
                    genai.protos.Content(
                        parts=[genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name="search_codes",
                                response={"result": tool_result}
                            )
                        )]
                    )
                )
            else:
                # Unknown tool, break to avoid infinite loop or error
                logger.warning(f"Unknown tool call: {fc.name}")
                break
                
        return response.text, thread_id

    except Exception as e:
        logger.exception("Error communicating with Gemini")
        raise RuntimeError("Error communicating with Gemini") from e