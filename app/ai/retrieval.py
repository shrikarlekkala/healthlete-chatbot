"""
retrieval.py — Vector search and threshold filtering
======================================================
"""

import logging
from typing import Dict, List, Tuple

from app.core.config import RETRIEVAL_LIMIT, SIMILARITY_THRESHOLD
from app.ai.embeddings import embed_query
from app.ai import prompts
from app.repositories.profile import search_similar_chunks

log = logging.getLogger("healthlete.retrieval")


def retrieve_chunks(athlete_id: str, query: str) -> List[Dict]:
    """Nearest chunks for THIS athlete id only, with cosine distances."""
    embedding = embed_query(query)
    return search_similar_chunks(athlete_id, embedding, RETRIEVAL_LIMIT)


def threshold_filter(rows: List[Dict]) -> Tuple[List[Dict], bool]:
    """Drops chunks beyond the similarity threshold.

    Returns (kept_chunks, was_weak).
    was_weak=True means nothing (or almost nothing) survived the threshold,
    so the profile data alone cannot be trusted to answer.
    """
    kept = [r for r in rows if r["distance"] <= SIMILARITY_THRESHOLD]
    return kept, (len(kept) == 0)


def build_context(rows: List[Dict]) -> str:
    """Stitches the kept chunks into one readable context block."""
    if not rows:
        return prompts.NO_PROFILE_DATA_REPLY
    ordered = sorted(rows, key=lambda r: r["index"])
    lines = [r["text"].strip() for r in ordered]
    return "\n".join([prompts.CONTEXT_HEADER] + lines + [prompts.CONTEXT_FOOTER])
