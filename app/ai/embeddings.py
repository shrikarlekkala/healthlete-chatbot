"""
embeddings.py - Vector embedding generation with in-memory LRU cache
====================================================================
"""

from functools import lru_cache
from typing import List, Tuple

from app.core.config import EMBEDDING_MODEL
from app.core.openai_client import get_openai_client, get_async_openai_client


@lru_cache(maxsize=1024)
def _embed_query_cached(text: str) -> Tuple[float, ...]:
    client = get_openai_client()
    return tuple(client.embeddings.create(input=text, model=EMBEDDING_MODEL).data[0].embedding)


def embed_query(text: str) -> List[float]:
    """Creates a vector embedding for a single text query (sync, cached)."""
    normalized = (text or "").strip()
    return list(_embed_query_cached(normalized))


# In-memory dictionary for non-blocking async embedding cache
_async_embed_cache: dict = {}


async def async_embed_query(text: str) -> List[float]:
    """Creates a vector embedding asynchronously without blocking event loop."""
    normalized = (text or "").strip()
    cached = _async_embed_cache.get(normalized)
    if cached is not None:
        return cached

    client = get_async_openai_client()
    res = await client.embeddings.create(input=normalized, model=EMBEDDING_MODEL)
    emb = res.data[0].embedding
    if len(_async_embed_cache) < 1024:
        _async_embed_cache[normalized] = emb
    return emb


def embed_batch(texts: list) -> list:
    """Creates vector embeddings for a batch of texts."""
    client = get_openai_client()
    response = client.embeddings.create(input=texts, model=EMBEDDING_MODEL)
    return [item.embedding for item in response.data]
