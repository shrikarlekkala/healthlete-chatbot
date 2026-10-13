"""
chat.py — Main chat pipeline and answer formatting
====================================================
Migrated from the original chat.py. Relies on extracted logic in
retrieval.py, web_search.py, prompts.py, and embeddings.py.
"""

import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import anyio

from app.core.config import CHAT_MODEL, MAX_TOKENS, TEMPERATURE, HISTORY_TURNS, SIMILARITY_THRESHOLD
from app.core.openai_client import get_openai_client, get_async_openai_client
from app.ai import prompts
from app.ai.retrieval import retrieve_chunks, threshold_filter, build_context
from app.ai.web_search import web_search_completion, web_search_stream
from app.utils.text import parse_decision, sanitize_answer
from app.utils.format import format_bullets

log = logging.getLogger("healthlete.chat")


# =====================================================================
# HISTORY & ROUTING
# =====================================================================

def trim_history(chat_history: List[Dict], turns: Optional[int] = None) -> List[Dict]:
    turns = HISTORY_TURNS if turns is None else turns
    cleaned = []
    for turn in chat_history or []:
        role = (turn.get("role") or "").strip().lower()
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            cleaned.append({"role": role, "content": content})
    return cleaned[-(turns * 2):] if turns else cleaned


# =====================================================================
# MAIN PIPELINE
# =====================================================================

def chat_completion(messages: List[Dict], model: str = CHAT_MODEL,
                    temperature: Optional[float] = None,
                    max_tokens: Optional[int] = None) -> str:
    client = get_openai_client()
    kwargs: Dict = {"model": model, "messages": messages}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    response = client.chat.completions.create(**kwargs)
    return (response.choices[0].message.content or "").strip()


def ask(athlete_id: str, user_query: str, chat_history: List[Dict] = None,
        athlete_name: Optional[str] = None) -> Dict:
    """Full pipeline for one question. Returns the answer dict with trace."""
    trace = {
        "athlete_id": athlete_id,
        "question": user_query,
        "timestamp": datetime.now().isoformat(),
        "stages": {},
    }
    t_total = time.time()

    # ---- history -----------------------------------------------------
    t0 = time.time()
    history = trim_history(chat_history)
    trace["stages"]["history"] = round(time.time() - t0, 3)

    # ---- retrieval ---------------------------------------------------
    t0 = time.time()
    rows = retrieve_chunks(athlete_id, user_query)
    from app.repositories.profile import get_profile_name
    profile_name = athlete_name or (rows[0]["profile_name"] if rows else get_profile_name(athlete_id))
    trace["athlete_name"] = profile_name
    trace["stages"]["retrieval"] = round(time.time() - t0, 3)
    trace["retrieved_chunks"] = len(rows)
    if rows:
        trace["best_distance"] = round(rows[0]["distance"], 4)
    log.info("TRACE id=%s stage=retrieval chunks=%s best_distance=%s time=%.3fs",
             athlete_id, len(rows),
             round(rows[0]["distance"], 4) if rows else None,
             trace["stages"]["retrieval"])

    # ---- threshold filter --------------------------------------------
    t0 = time.time()
    kept, weak = threshold_filter(rows)
    trace["stages"]["filtering"] = round(time.time() - t0, 3)
    trace["chunks_after_threshold"] = len(kept)
    trace["weak_retrieval"] = weak
    log.info("TRACE id=%s stage=filter threshold=%s kept=%s weak=%s time=%.3fs",
             athlete_id, SIMILARITY_THRESHOLD, len(kept), weak,
             trace["stages"]["filtering"])

    # ---- stage 1: profile answer -------------------------------------
    t0 = time.time()
    instructions = (prompts.CORE_ANALYST_INSTRUCTIONS + "\n"
                    + prompts.STAGE2_PROFILE_INSTRUCTIONS + "\n"
                    + prompts.OFF_TOPIC_INSTRUCTIONS)
    user_message = prompts.build_profile_user_message(
        profile_name, build_context(kept), user_query, weak)

    # When no chunks match the threshold, only routing decision is needed (fast path)
    stage1_tokens = 100 if not kept else MAX_TOKENS
    raw_answer = chat_completion(
        messages=(
            [{"role": "system", "content": instructions}]
            + history
            + [{"role": "user", "content": user_message}]
        ),
        temperature=TEMPERATURE,
        max_tokens=stage1_tokens,
    )
    trace["stages"]["profile_answer"] = round(time.time() - t0, 3)

    decision, body = parse_decision(raw_answer)
    decision = decision or "PROFILE"
    trace["decision"] = decision
    log.info("TRACE id=%s stage=profile_answer decision=%s time=%.3fs",
             athlete_id, decision, trace["stages"]["profile_answer"])

    # ---- route: off topic ---------------------------------------------
    if decision == "OFF_TOPIC":
        trace["path"] = "off_topic"
        trace["answer"] = prompts.OFF_TOPIC_REPLY
        trace["stages"]["total"] = round(time.time() - t_total, 3)
        log.info("TRACE id=%s path=off_topic total=%.3fs",
                 athlete_id, trace["stages"]["total"])
        return trace

    # ---- route: web search fallback ------------------------------------
    if decision == "INSUFFICIENT" or (decision == "PROFILE" and not kept):
        log.info("TRACE id=%s stage=web_search start", athlete_id)
        t0 = time.time()
        top_text = build_context(sorted(rows, key=lambda r: r["distance"])[:5])
        try:
            web_answer, sources = web_search_completion(
                profile_name=profile_name,
                top_chunks_text=top_text,
                partial_answer=body if decision == "INSUFFICIENT" else "",
                gap="",
                question=user_query,
                history=history,
            )
            final = format_bullets(sanitize_answer(web_answer)) if web_answer else prompts.WEB_SEARCH_FAILED_REPLY
            trace["web_sources"] = sources
            trace["web_search_used"] = True
            trace["path"] = "web_search"
        except Exception as exc:
            log.error("TRACE id=%s stage=web_search failed: %s", athlete_id, exc)
            final = format_bullets(sanitize_answer(body)) if body else prompts.WEB_SEARCH_FAILED_REPLY
            trace["web_search_used"] = False
            trace["path"] = "profile_only"
            trace["web_search_error"] = str(exc)
        trace["stages"]["web_search"] = round(time.time() - t0, 3)
        trace["answer"] = final
        trace["stages"]["total"] = round(time.time() - t_total, 3)
        log.info("TRACE id=%s path=%s web_used=%s total=%.3fs",
                 athlete_id, trace["path"], trace["web_search_used"],
                 trace["stages"]["total"])
        return trace

    # ---- route: profile answer ------------------------------------------
    if body:
        body = format_bullets(sanitize_answer(body))
    trace["path"] = "profile"
    trace["web_search_used"] = False
    trace["answer"] = body or (prompts.NO_PROFILE_DATA_REPLY if not rows
                               else prompts.INSUFFICIENT_DATA_REPLY)
    trace["stages"]["total"] = round(time.time() - t_total, 3)
    log.info("TRACE id=%s path=profile answer_len=%s total=%.3fs",
             athlete_id, len(trace["answer"]), trace["stages"]["total"])
    return trace


# =====================================================================
# STREAMING PIPELINE (SSE)
# =====================================================================

async def chat_completion_stream(messages: List[Dict], model: str = CHAT_MODEL,
                                 temperature: Optional[float] = None,
                                 max_tokens: Optional[int] = None):
    """Async generator yielding content tokens from a streaming OpenAI response."""
    client = get_async_openai_client()
    kwargs: Dict = {"model": model, "messages": messages, "stream": True}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    response = await client.chat.completions.create(**kwargs)
    async for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def ask_stream(athlete_id: str, user_query: str,
                     chat_history: List[Dict] = None,
                     athlete_name: Optional[str] = None):
    """Full streaming pipeline. Yields SSE event dicts.

    Event types:
      {"type": "meta",    "athlete_id": ..., "profile_name": ...}
      {"type": "content", "delta": ...}
      {"type": "status",  "message": ...}
      {"type": "done",    "path": ..., "decision": ..., "answer": ..., "chat_history": [...]}
    """

    # ---- retrieval (sync → threadpool) --------------------------------
    def _do_retrieval():
        rows = retrieve_chunks(athlete_id, user_query)
        from app.repositories.profile import get_profile_name
        name = athlete_name or (
            rows[0]["profile_name"] if rows else get_profile_name(athlete_id)
        )
        kept, weak = threshold_filter(rows)
        return rows, kept, weak, name

    try:
        rows, kept, weak, profile_name = await anyio.to_thread.run_sync(_do_retrieval)
    except Exception as exc:
        log.error("ask_stream retrieval failed: %s", exc)
        yield {"type": "error", "message": f"Retrieval error: {exc}"}
        return

    yield {"type": "meta", "athlete_id": athlete_id, "profile_name": profile_name}

    # ---- prepare messages --------------------------------------------
    history = trim_history(chat_history)
    instructions = (prompts.CORE_ANALYST_INSTRUCTIONS + "\n"
                    + prompts.STAGE2_PROFILE_INSTRUCTIONS + "\n"
                    + prompts.OFF_TOPIC_INSTRUCTIONS)
    user_message = prompts.build_profile_user_message(
        profile_name, build_context(kept), user_query, weak)

    stage1_tokens = 100 if not kept else MAX_TOKENS
    messages = (
        [{"role": "system", "content": instructions}]
        + history
        + [{"role": "user", "content": user_message}]
    )

    # ---- stream with decision-line buffer ----------------------------
    buffer = ""
    decision_found = False
    decision = None
    full_answer_parts: List[str] = []
    needs_web_search = False

    try:
        async for token in chat_completion_stream(
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=stage1_tokens,
        ):
            if not decision_found:
                buffer += token
                if "\n" in buffer:
                    first_line, rest = buffer.split("\n", 1)
                    decision, _ = parse_decision(first_line)
                    decision = decision or "PROFILE"
                    decision_found = True

                    if decision == "OFF_TOPIC":
                        break

                    if decision == "INSUFFICIENT" or (decision == "PROFILE" and not kept):
                        needs_web_search = True
                        break

                    # PROFILE path — yield text after the decision line
                    if rest:
                        full_answer_parts.append(rest)
                        yield {"type": "content", "delta": rest}
            else:
                full_answer_parts.append(token)
                yield {"type": "content", "delta": token}
    except Exception as exc:
        log.error("ask_stream LLM streaming failed: %s", exc)
        yield {"type": "error", "message": f"LLM error: {exc}"}
        return

    # Handle case where no newline ever appeared in the output
    if not decision_found:
        decision, body = parse_decision(buffer)
        decision = decision or "PROFILE"
        if decision == "OFF_TOPIC":
            pass  # handled below
        elif decision == "INSUFFICIENT" or (decision == "PROFILE" and not kept):
            needs_web_search = True
        elif body:
            full_answer_parts.append(body)
            yield {"type": "content", "delta": body}

    # ---- route: off_topic --------------------------------------------
    path = "profile"
    if decision == "OFF_TOPIC":
        full_answer_parts = [prompts.OFF_TOPIC_REPLY]
        yield {"type": "content", "delta": prompts.OFF_TOPIC_REPLY}
        path = "off_topic"

    # ---- route: web search fallback ----------------------------------
    elif needs_web_search:
        path = "web_search"
        yield {"type": "status", "message": "Searching public sources..."}

        partial_body = ""
        if decision == "INSUFFICIENT" and buffer:
            _, partial_body = parse_decision(buffer)

        top_text = build_context(sorted(rows, key=lambda r: r["distance"])[:5])
        web_tokens_received = False
        try:
            async for delta in web_search_stream(
                profile_name=profile_name,
                top_chunks_text=top_text,
                partial_answer=partial_body,
                gap="",
                question=user_query,
                history=history,
            ):
                web_tokens_received = True
                full_answer_parts.append(delta)
                yield {"type": "content", "delta": delta}
        except Exception as exc:
            log.error("Stream web_search failed: %s", exc)

        if not web_tokens_received:
            fallback = (format_bullets(sanitize_answer(partial_body))
                        if partial_body else prompts.WEB_SEARCH_FAILED_REPLY)
            full_answer_parts.append(fallback)
            yield {"type": "content", "delta": fallback}
            if partial_body:
                path = "profile_only"

    # ---- build final answer and updated history ----------------------
    full_answer = "".join(full_answer_parts).strip()
    if not full_answer:
        full_answer = (prompts.NO_PROFILE_DATA_REPLY if not rows
                       else prompts.INSUFFICIENT_DATA_REPLY)

    turns = max(1, HISTORY_TURNS)
    new_turns = [
        {"role": "user", "content": user_query},
        {"role": "assistant", "content": full_answer},
    ]
    combined = [t for t in history
                if t.get("role") in ("user", "assistant")
                and t.get("content", "").strip()]
    combined.extend(new_turns)
    trimmed = combined[-(turns * 2):]
    updated_history = [{"role": t["role"], "content": t["content"]} for t in trimmed]

    yield {
        "type": "done",
        "athlete_id": athlete_id,
        "profile_name": profile_name,
        "path": path,
        "decision": decision,
        "answer": full_answer,
        "chat_history": updated_history,
    }
