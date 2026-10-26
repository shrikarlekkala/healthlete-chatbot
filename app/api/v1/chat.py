"""
chat.py - Marketing analytics chat endpoint with security enforcement
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest
from app.core.security import enforce_security, validate_payload_message
from app.ai import chat

log = logging.getLogger("healthlete.api.chat")
router = APIRouter(tags=["Athlete Analytics"])


def clean_id(raw: str) -> str:
    cleaned = (raw or "").strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="A non-empty athlete_id is required.")
    return cleaned




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
    2. IP rate limiting (max 20 requests per minute).
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
