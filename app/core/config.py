"""
config.py — Centralized application configuration
====================================================
All environment variables are read here once. Every other module imports
from this file instead of calling os.getenv() directly.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ── API ──────────────────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "3236"))
THREAD_POOL_LIMIT: int = int(os.getenv("THREAD_POOL_LIMIT", "100"))
ALLOWED_ORIGINS: list = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()
]

# ── Database ─────────────────────────────────────────────────────────────
DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
DB_USER: str = os.getenv("DB_USER", "postgres")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
DB_NAME: str = os.getenv("DB_NAME", "healthlete")
DB_POOL_MIN: int = int(os.getenv("DB_POOL_MIN", "2"))
DB_POOL_MAX: int = int(os.getenv("DB_POOL_MAX", "20"))
DB_POOL_TIMEOUT: float = float(os.getenv("DB_POOL_TIMEOUT", "10.0"))

# ── OpenAI ───────────────────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
CHAT_MODEL: str = os.getenv("CHAT_MODEL", "gpt-4o")
WEB_SEARCH_MODEL: str = os.getenv("WEB_SEARCH_MODEL", "gpt-4.1")

# ── Chat pipeline ────────────────────────────────────────────────────────
RETRIEVAL_LIMIT: int = int(os.getenv("RETRIEVAL_LIMIT", "8"))
SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.75"))
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "800"))
TEMPERATURE: float = float(os.getenv("CHAT_TEMPERATURE", "0.2"))
HISTORY_TURNS: int = int(os.getenv("HISTORY_TURNS", "3"))
