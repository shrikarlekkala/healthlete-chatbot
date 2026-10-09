"""
openai_client.py — Thread-safe singleton OpenAI client
=======================================================
"""

import threading
from typing import Optional

from openai import OpenAI

from app.core.config import OPENAI_API_KEY

client_instance: Optional[OpenAI] = None
client_lock = threading.Lock()


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
