from __future__ import annotations

import logging
import os
import json
from typing import Optional, Tuple, List
from functools import lru_cache
import re

import google.generativeai as genai
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
        
        # Fallback: If no results, try splitting the query into keywords
        if not results and len(query.split()) > 1:
            logger.info(f"No exact match for '{query}', trying keyword search.")
            keywords = [w for w in query.split() if len(w) > 3] # Filter out short words
            if keywords:
                keyword_filters = []
                for word in keywords:
                    keyword_filters.append(Code.name.ilike(f"%{word}%"))
                    keyword_filters.append(Code.description.ilike(f"%{word}%"))
                    keyword_filters.append(Code.chapter.ilike(f"%{word}%"))
                    keyword_filters.append(Code.section.ilike(f"%{word}%"))
                
                # Search for any of the keywords
                results = db.query(Code).filter(or_(*keyword_filters)).limit(5).all()

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

def _extract_cited_code_ids(message: str) -> List[int]:
    """
    Find all code IDs cited in the assistant's reply using the [Code: <id>] pattern.
    """
    if not message:
        return []
    ids: List[int] = []
    for match in re.findall(r"\[Code:\s*(\d+)\]", message):
        try:
            ids.append(int(match))
        except ValueError:
            continue
    return ids

def _format_reference_line(code: Code) -> str:
    """
    Build a human-readable reference string for a code entry.
    """
    location_parts = []
    if code.chapter:
        location_parts.append(f"Chapter {code.chapter}")
    if code.section:
        location_parts.append(f"Section {code.section}")
    location = " ".join(location_parts)

    summary = code.name or code.description or ""
    details = " - ".join(part for part in (location, summary) if part)
    return f"- [Code: {code.id}] {details}".strip()

def _apply_reference_guards(raw_reply: str, db: Session) -> str:
    """
    Ensure every cited code exists in the database and append a verified References section.
    Unknown codes are called out explicitly so we never silently cite a missing record.
    """
    cited_ids = _extract_cited_code_ids(raw_reply)
    if not cited_ids:
        return raw_reply.strip()

    codes = db.query(Code).filter(Code.id.in_(cited_ids)).all()
    code_by_id = {c.id: c for c in codes}

    # Replace any missing citations with an explicit note
    safe_reply = raw_reply or ""
    for missing_id in [cid for cid in cited_ids if cid not in code_by_id]:
        safe_reply = re.sub(
            rf"\[Code:\s*{re.escape(str(missing_id))}\]",
            f"[Code not found in database: {missing_id}]",
            safe_reply,
        )

    # Preserve the order of appearance while deduplicating
    ordered_codes: List[Code] = []
    seen_ids = set()
    for cid in cited_ids:
        if cid in code_by_id and cid not in seen_ids:
            ordered_codes.append(code_by_id[cid])
            seen_ids.add(cid)

    references_lines = [_format_reference_line(code) for code in ordered_codes]
    if not references_lines:
        references_lines = ["- No matching codes found in the database for the cited IDs."]

    references_block = "References:\n" + "\n".join(references_lines)

    safe_reply = safe_reply.strip()
    if safe_reply:
        return f"{safe_reply}\n\n{references_block}"
    return references_block

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
    3. After answering, end with a "References:" section listing each cited code (id, chapter, section, title) that came from search_codes. If no code is found, write "References: none found in database".
    4. Never cite a code that was not returned from search_codes.
    5. Be concise and helpful.
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

        while True:
            candidate = response.candidates[0] if response.candidates else None
            if not candidate or not candidate.content.parts:
                break

            part = candidate.content.parts[0]
            if not getattr(part, "function_call", None):
                break

            fc = part.function_call
            if fc.name == "search_codes":
                query = fc.args.get("query", "") if hasattr(fc, "args") else ""
                logger.info("Gemini requested search_codes with query: %s", query)

                tool_result = search_codes(db, query)

                response = await chat.send_message_async(
                    genai.protos.Content(
                        parts=[
                            genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name="search_codes",
                                    response={"result": tool_result}
                                )
                            )
                        ]
                    )
                )
                continue

            logger.warning("Unknown tool call: %s", fc.name if hasattr(fc, "name") else fc)
            break

        # Post-process to ensure references are verified against the database
        verified_reply = _apply_reference_guards(response.text or "", db)

        return verified_reply, thread_id

    except Exception as e:
        logger.exception("Error running assistant with Gemini: %s", e)
        raise RuntimeError("Error running assistant with Gemini") from e

def _validate_evaluation_json(json_str: str, db: Session, num_images: int = 0) -> str:
    """
    Parses the evaluation JSON, verifies that all cited code_ids exist in the DB,
    and removes invalid code_ids to prevent broken links.
    Returns the cleaned JSON string.
    """
    try:
        # Use regex to find the first JSON object in the string
        # This handles cases where the model adds conversational filler or markdown blocks
        match = re.search(r'\{.*\}', json_str, re.DOTALL)
        if match:
            cleaned_str = match.group(0)
        else:
            # Fallback to original string if no JSON object found (though likely to fail parsing)
            cleaned_str = json_str.strip()

        data = json.loads(cleaned_str)
        if not isinstance(data, dict):
            return json_str
            
        potential_violations = data.get("potential_violations", [])
        if not potential_violations:
            return json_str
            
        valid_violations = []
        for v in potential_violations:
            code_id = v.get("code_id")
            if code_id:
                # Verify code exists
                code = db.query(Code).filter(Code.id == code_id).first()
                if code:
                    # Ensure related_image_indices is a list of ints if present
                    # Ensure related_image_indices is a list of ints if present
                    if "related_image_indices" in v:
                        if not isinstance(v["related_image_indices"], list):
                            v["related_image_indices"] = []
                        
                        # Filter indices to be within valid range [1, num_images]
                        if num_images > 0:
                            valid_indices = [
                                idx for idx in v["related_image_indices"] 
                                if isinstance(idx, int) and 1 <= idx <= num_images
                            ]
                            v["related_image_indices"] = valid_indices
                    
                    valid_violations.append(v)
                else:
                    logger.warning(f"Hallucinated code_id {code_id} removed from evaluation.")
                    # User requested NO made up codes, so we drop this violation entirely
                    continue
            else:
                # If no code_id is provided, we also drop it to enforce "select from available codes"
                continue
        
        data["potential_violations"] = valid_violations
        return json.dumps(data)
    except json.JSONDecodeError:
        logger.warning("Failed to parse evaluation JSON for validation")
        return json_str
    except Exception as e:
        logger.exception("Error validating evaluation JSON: %s", e)
        return json_str

async def evaluate_image_for_violation(
    images_data: List[Tuple[bytes, str]],
    db: Session
) -> str:
    """
    Analyze images for potential code violations using Gemini Vision and RAG.
    
    Args:
        images_data: List of (image_bytes, mime_type) tuples.
        db: Database session.
        
    Returns:
        JSON string with analysis results.
    """
    _configure_gemini()
    
    tools_config = [
        {
            "function_declarations": [
                {
                    "name": "search_codes",
                    "description": "Search for municipal codes/laws based on a query.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "query": {
                                "type": "STRING",
                                "description": "The search term."
                            }
                        },
                        "required": ["query"]
                    }
                }
            ]
        }
    ]

    system_instruction = """You are an expert municipal code enforcement officer.
    Analyze the provided image(s) to identify potential code violations.
    
    1. Describe what you see in the image(s).
    2. Search for relevant municipal codes using 'search_codes'.
       - IMPORTANT: Use SHORT, SINGLE KEYWORDS for best results (e.g. "door", "trash", "paint").
       - Do NOT use long sentences or natural language queries.
       - If your first search yields no results, try synonyms.
       - For graffiti, search for "defacement", "graffiti", "damage".
       - For tall grass, search for "weeds", "grass".
       - For trash, search for "rubbish", "garbage".
    3. If violations are found, list all relevant violations (typically 2-5).
    4. For each violation, provide a confidence score (0-100%) indicating how certain you are that this code applies.
    5. Identify which images (by index, starting at 1) show this specific violation.
    6. Provide a recommendation.
    
    CRITICAL RULES:
    - You must ONLY cite codes that are explicitly returned by the 'search_codes' tool.
    - Do NOT hallucinate or make up code IDs.
    - If you find a relevant code in the search results, use its exact 'id' for 'code_id'.
    - 'related_image_indices' MUST only contain integers corresponding to the images provided (e.g. if 1 image is provided, only [1] is valid).
    
    Output MUST be valid JSON with this structure:
    {
        "observation": "...",
        "potential_violations": [
            {
                "description": "...",
                "code_id": 123, # Integer ID from search_codes result, or null
                "code_citation": "Chapter X, Section Y",
                "confidence": 95, # Integer percentage
                "related_image_indices": [1] # List of integer indices of images showing this violation
            }
        ],
        "recommendation": "..."
    }
    """

    model = genai.GenerativeModel(
        model_name="gemini-flash-latest",
        tools=tools_config,
        system_instruction=system_instruction
    )

    # Prepare content
    content_parts = []
    for img_bytes, mime_type in images_data:
        content_parts.append({
            "mime_type": mime_type,
            "data": img_bytes
        })
    
    content_parts.append("Analyze these images for code violations.")

    chat = model.start_chat(history=[])
    
    try:
        response = await chat.send_message_async(content_parts)
        
        # Handle tool calls (loop)
        while True:
            part = response.candidates[0].content.parts[0]
            if not part.function_call:
                break
            
            fc = part.function_call
            if fc.name == "search_codes":
                query = fc.args["query"]
                logger.info(f"Gemini requested search_codes for image analysis with query: {query}")
                
                tool_result = search_codes(db, query)
                
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
                break
        
        raw_json = response.text
        validated_json = _validate_evaluation_json(raw_json, db, num_images=len(images_data))
        return validated_json
        
    except Exception as e:
        logger.exception("Error analyzing image with Gemini")
        raise RuntimeError("Error analyzing image with Gemini") from e
