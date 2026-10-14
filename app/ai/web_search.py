"""
web_search.py - Web search fallback via OpenAI Responses API
==============================================================
"""

import logging
import asyncio
from typing import Dict, List, Tuple

from app.core.config import WEB_SEARCH_MODEL, MAX_TOKENS, TEMPERATURE
from app.core.openai_client import get_openai_client, get_async_openai_client
from app.ai import prompts

log = logging.getLogger("healthlete.web_search")


def web_search_completion(profile_name: str, top_chunks_text: str,
                          partial_answer: str, gap: str, question: str,
                          history: List[Dict]) -> Tuple[str, List[Dict]]:
    """Calls the OpenAI Responses API with web search enabled (GPT-4.1)."""
    client = get_openai_client()

    instructions = prompts.CORE_ANALYST_INSTRUCTIONS + "\n" + prompts.WEB_SEARCH_INSTRUCTIONS

    input_messages = [{"role": t["role"], "content": t["content"]} for t in history or []]
    input_messages.append({"role": "user", "content": prompts.build_web_user_message(
        profile_name, top_chunks_text, partial_answer, gap, question)})

    last_error = None
    for tool_type in ("web_search", "web_search_preview"):
        try:
            response = client.responses.create(
                model=WEB_SEARCH_MODEL,
                instructions=instructions,
                input=input_messages,
                tools=[{"type": tool_type}],
                max_output_tokens=min(MAX_TOKENS, 800),
                temperature=TEMPERATURE,
            )
            return read_response_text(response), read_citations(response)
        except Exception as exc:
            last_error = exc
            log.warning("Web search tool '%s' failed: %s", tool_type, exc)

    raise last_error if last_error else RuntimeError("Web search could not start")


async def web_search_stream(profile_name: str, top_chunks_text: str,
                            partial_answer: str, gap: str, question: str,
                            history: List[Dict]):
    """Streams web search completion tokens via OpenAI Responses API (AsyncOpenAI).
    Yields string content deltas directly.
    """
    client = get_async_openai_client()

    instructions = prompts.CORE_ANALYST_INSTRUCTIONS + "\n" + prompts.WEB_SEARCH_INSTRUCTIONS

    input_messages = [{"role": t["role"], "content": t["content"]} for t in history or []]
    input_messages.append({"role": "user", "content": prompts.build_web_user_message(
        profile_name, top_chunks_text, partial_answer, gap, question)})

    last_error = None
    for tool_type in ("web_search", "web_search_preview"):
        try:
            stream = await client.responses.create(
                model=WEB_SEARCH_MODEL,
                instructions=instructions,
                input=input_messages,
                tools=[{"type": tool_type}],
                max_output_tokens=min(MAX_TOKENS, 800),
                temperature=TEMPERATURE,
                stream=True,
            )
            try:
                async for event in stream:
                    if getattr(event, "type", "") == "response.output_text.delta":
                        delta = getattr(event, "delta", "")
                        if delta:
                            yield delta
            except (GeneratorExit, asyncio.CancelledError):
                return
            return
        except (GeneratorExit, asyncio.CancelledError):
            return
        except Exception as exc:
            last_error = exc
            log.warning("Web search stream tool '%s' failed: %s", tool_type, exc)

    if last_error:
        raise last_error


def read_response_text(response) -> str:
    text = (getattr(response, "output_text", None) or "").strip()
    if text:
        return text
    parts = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            chunk = getattr(content, "text", None)
            if isinstance(chunk, str):
                parts.append(chunk)
    return "\n".join(parts).strip()


def read_citations(response) -> List[Dict]:
    sources, seen = [], set()
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", "") != "message":
            continue
        for content in getattr(item, "content", []) or []:
            for annotation in getattr(content, "annotations", []) or []:
                if getattr(annotation, "type", "") == "url_citation":
                    url = getattr(annotation, "url", None)
                    title = getattr(annotation, "title", None) or url
                    if url and url not in seen:
                        seen.add(url)
                        sources.append({"url": url, "title": title})
    return sources
