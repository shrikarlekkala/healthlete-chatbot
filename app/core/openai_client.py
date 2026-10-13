"""
openai_client.py — Thread-safe singleton OpenAI client
=======================================================
"""

import threading
from typing import Optional

from openai import AsyncOpenAI, OpenAI

from app.core.config import OPENAI_API_KEY

client_instance: Optional[OpenAI] = None
client_lock = threading.Lock()

async_client_instance: Optional[AsyncOpenAI] = None
async_client_lock = threading.Lock()


def get_openai_client() -> OpenAI:
    """Returns a shared, thread-safe OpenAI client with connection pooling,
    automatic retries, and timeout configuration."""
    global client_instance
    if client_instance is None:
        with client_lock:
            if client_instance is None:
                client_instance = OpenAI(
                    api_key=OPENAI_API_KEY,
                    max_retries=2,
                    timeout=30.0,
                )
    return client_instance


def get_async_openai_client() -> AsyncOpenAI:
    """Returns a shared AsyncOpenAI client for streaming operations."""
    global async_client_instance
    if async_client_instance is None:
        with async_client_lock:
            if async_client_instance is None:
                async_client_instance = AsyncOpenAI(
                    api_key=OPENAI_API_KEY,
                    max_retries=2,
                    timeout=30.0,
                )
    return async_client_instance
