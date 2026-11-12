"""
service.py - Brand assistant pipeline.

plan()          question -> tool calls with JSON criteria (one fast call)
answer_stream() question + backend results -> streamed answer
"""

import json
import logging
import time
from typing import Any, AsyncIterator, Dict, List

from app.ai.assistant import prompts
from app.ai.assistant.tools import ANSWER_DIRECTLY, TOOL_NAMES, TOOLS
from app.core.config import (
    ASSISTANT_ANSWER_MODEL,
    ASSISTANT_MAX_TOKENS,
    ASSISTANT_PLAN_MODEL,
    HISTORY_TURNS,
)
from app.core.openai_client import get_async_openai_client

log = logging.getLogger("healthlete.assistant")

MAX_TOOL_CALLS = 4
HISTORY_CHAR_LIMIT = 600


def _history(chat_history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    cleaned = []
    for turn in chat_history or []:
        role = (turn.get("role") or "").strip().lower()
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            cleaned.append({"role": role, "content": content[:HISTORY_CHAR_LIMIT]})
    return cleaned[-(max(1, HISTORY_TURNS) * 2):]


def _parse_arguments(raw: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


async def plan(
    message: str,
    chat_history: List[Dict[str, str]],
    catalog: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    started = time.perf_counter()
    response = await get_async_openai_client().chat.completions.create(
        model=ASSISTANT_PLAN_MODEL,
        messages=[
            {"role": "system", "content": prompts.PLANNER_INSTRUCTIONS},
            {"role": "system", "content": prompts.catalog_message(catalog)},
            {"role": "system", "content": prompts.brand_message(catalog)},
            *_history(chat_history),
            {"role": "user", "content": message},
        ],
        tools=TOOLS,
        tool_choice="required",
        parallel_tool_calls=True,
        temperature=0,
        max_tokens=300,
    )

    calls: List[Dict[str, Any]] = []
    for tool_call in response.choices[0].message.tool_calls or []:
        name = tool_call.function.name
        if name in TOOL_NAMES:
            calls.append({"name": name, "arguments": _parse_arguments(tool_call.function.arguments)})

    calls = calls[:MAX_TOOL_CALLS] or [{"name": ANSWER_DIRECTLY, "arguments": {}}]
    log.info(
        "assistant.plan tools=%s elapsed=%.3fs",
        ",".join(call["name"] for call in calls),
        time.perf_counter() - started,
    )
    return calls


async def answer_stream(
    message: str,
    chat_history: List[Dict[str, str]],
    tool_results: List[Dict[str, Any]],
    surface: str,
) -> AsyncIterator[Dict[str, Any]]:
    started = time.perf_counter()
    instructions = prompts.ANSWER_INSTRUCTIONS
    if surface == "discover":
        instructions += prompts.DISCOVER_SURFACE_NOTE

    parts: List[str] = []
    try:
        stream = await get_async_openai_client().chat.completions.create(
            model=ASSISTANT_ANSWER_MODEL,
            messages=[
                {"role": "system", "content": instructions},
                *_history(chat_history),
                {"role": "user", "content": prompts.answer_user_message(message, tool_results)},
            ],
            temperature=0.3,
            max_tokens=ASSISTANT_MAX_TOKENS,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                parts.append(delta)
                yield {"type": "content", "delta": delta}
    except Exception as exc:  # noqa: BLE001 - reported to the caller as an SSE event
        log.error("assistant.answer failed: %s", exc)
        yield {"type": "error", "message": "Unable to write an answer right now."}
        return

    answer = "".join(parts).strip()
    log.info(
        "assistant.answer surface=%s chars=%s elapsed=%.3fs",
        surface,
        len(answer),
        time.perf_counter() - started,
    )
    yield {"type": "done", "answer": answer}
