"""
embeddings.py — Vector embedding generation
=============================================
"""

from app.core.config import EMBEDDING_MODEL
from app.core.openai_client import get_openai_client


def embed_query(text: str) -> list:
    """Creates a vector embedding for a single text query."""
    client = get_openai_client()
    return client.embeddings.create(input=text, model=EMBEDDING_MODEL).data[0].embedding


def embed_batch(texts: list) -> list:
    """Creates vector embeddings for a batch of texts."""
    client = get_openai_client()
    response = client.embeddings.create(input=texts, model=EMBEDDING_MODEL)
    return [item.embedding for item in response.data]
