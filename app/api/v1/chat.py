"""
chat.py - Marketing analytics chat endpoint with security enforcement
"""

import json
import logging
import time
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest, ChatResponse, ChatMessage
from app.core.security import enforce_security, validate_payload_message
from app.ai import chat
from app.ai import prompts

log = logging.getLogger("healthlete.api.chat")
router = APIRouter(tags=["Athlete Analytics"])


def clean_id(raw: str) -> str:
    cleaned = (raw or "").strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="A non-empty athlete_id is required.")
    return cleaned


def build_updated_history(existing: List[ChatMessage], question: str,
                           answer: str, server_history: List[Dict]) -> List[ChatMessage]:
    """Returns the history the client should maintain for subsequent turns."""
    turns = max(1, chat.HISTORY_TURNS)
    new_turns: List[Dict] = [
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer},
    ]
    base = server_history if server_history else [m.model_dump() for m in existing]
    combined = [t for t in base if t.get("role") in ("user", "assistant")
                and t.get("content", "").strip()]
    combined.extend(new_turns)
    trimmed = combined[-(turns * 2):]
    return [ChatMessage(role=t["role"], content=t["content"]) for t in trimmed]


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Query Athlete Intelligence",
    dependencies=[Depends(enforce_security)],
)
def chat_endpoint(request: ChatRequest):
    """
    Execute strategic marketing and commercial fit analysis for an athlete.

    Security checks enforced:
    1. Valid X-API-Key header required.
    2. IP rate limiting (max 5 requests per minute).
    3. Maximum query payload length (500 characters).
    """
    athlete_id = clean_id(request.athlete_id)
    message = validate_payload_message(request.message)
    history = [m.model_dump() for m in request.chat_history]

    t_start = time.time()
    try:
        trace = chat.ask(
            athlete_id=athlete_id,
            user_query=message,
            chat_history=history,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {e}")

    answer = trace.get("answer") or prompts.NO_PROFILE_DATA_REPLY
    decision = trace.get("decision") or "PROFILE"
    path = trace.get("path") or "profile"

    server_history = trace.get("chat_history")
    updated_history = build_updated_history(
        request.chat_history, message, answer, server_history or [])

    elapsed = round(time.time() - t_start, 3)
    log.info("API /chat id=%s path=%s decision=%s answer_len=%s elapsed=%.3fs",
             athlete_id, path, decision, len(answer), elapsed)

    return ChatResponse(
        athlete_id=athlete_id,
        profile_name=trace.get("athlete_name"),
        answer=answer,
        path=path,
        decision=decision,
        chat_history=updated_history,
    )


@router.post(
    "/chat/stream",
    summary="Query Athlete Intelligence (Streaming SSE)",
    dependencies=[Depends(enforce_security)],
)
async def chat_stream_endpoint(request: ChatRequest):
    """
    SSE streaming version of the /chat endpoint.

    Security checks enforced:
    1. Valid X-API-Key header required.
    2. IP rate limiting (max 5 requests per minute).
    3. Maximum query payload length (500 characters).

    Event protocol:
      data: {"type": "meta", "athlete_id": ..., "profile_name": ...}
      data: {"type": "content", "delta": "..."}
      data: {"type": "done", "athlete_id": ..., "profile_name": ..., "path": ..., "decision": ..., "answer": ..., "chat_history": [...]}
    """
    athlete_id = clean_id(request.athlete_id)
    message = validate_payload_message(request.message)
    history = [m.model_dump() for m in request.chat_history]

    async def event_generator():
        async for event in chat.ask_stream(
            athlete_id=athlete_id,
            user_query=message,
            chat_history=history,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
