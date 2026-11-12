"""
assistant.py - Brand assistant endpoints (called only by the NestJS backend).

POST /assistant/plan            -> which tools to run, with JSON criteria
POST /assistant/answer/stream   -> SSE answer written from the tool results

No database or embeddings here: the backend runs the tools for the logged-in
brand and sends back only a small summary of the results.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.ai.assistant import service
from app.core.security import enforce_assistant_security, validate_payload_message
from app.schemas.assistant import (
    AssistantAnswerRequest,
    AssistantPlanRequest,
    AssistantPlanResponse,
    AssistantToolCall,
)

log = logging.getLogger("healthlete.api.assistant")
router = APIRouter(
    prefix="/assistant",
    tags=["Brand Assistant"],
    dependencies=[Depends(enforce_assistant_security)],
)

# Keeps the answer prompt small: the backend should send summaries, not full records.
MAX_TOOL_RESULTS_CHARS = 24_000


@router.post("/plan", response_model=AssistantPlanResponse, summary="Plan assistant tool calls")
async def plan_endpoint(request: AssistantPlanRequest):
    message = validate_payload_message(request.message)
    try:
        calls = await service.plan(
            message=message,
            chat_history=[m.model_dump() for m in request.chat_history],
            catalog=request.catalog.model_dump(),
        )
    except Exception as exc:  # noqa: BLE001
        log.error("assistant.plan failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The assistant could not understand that request right now.",
        )
    return AssistantPlanResponse(tool_calls=[AssistantToolCall(**call) for call in calls])


@router.post("/answer/stream", summary="Stream the assistant answer (SSE)")
async def answer_stream_endpoint(request: AssistantAnswerRequest):
    """
    Event protocol:
      data: {"type": "content", "delta": "..."}
      data: {"type": "done", "answer": "..."}
      data: {"type": "error", "message": "..."}
    """
    message = validate_payload_message(request.message)
    tool_results = [r.model_dump() for r in request.tool_results]
    if len(json.dumps(tool_results, ensure_ascii=False)) > MAX_TOOL_RESULTS_CHARS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Tool results are too large.",
        )

    async def event_generator():
        async for event in service.answer_stream(
            message=message,
            chat_history=[m.model_dump() for m in request.chat_history],
            tool_results=tool_results,
            surface=request.surface,
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
