"""
main.py — FastAPI application entry point
===========================================
Migrated from the original fast.py
"""

from contextlib import asynccontextmanager
import sys

import anyio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.core.config import API_HOST, API_PORT, THREAD_POOL_LIMIT, ALLOWED_ORIGINS
from app.core.database import init_db_pool, close_db_pool
from app.api.v1.router import api_router

# UTF-8 stdout configuration for Windows terminals
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Scale default worker thread capacity for high-concurrency requests
    try:
        anyio.to_thread.current_default_thread_limiter().total_tokens = THREAD_POOL_LIMIT
    except Exception:
        pass

    # Initialize connection pool on startup
    init_db_pool()
    yield
    # Close connection pool gracefully on shutdown
    close_db_pool()


TAGS_METADATA = [
    {
        "name": "System",
        "description": "System health, service availability, and diagnostics.",
    },
    {
        "name": "Athlete Ingestion",
        "description": "Athlete profile ingestion, normalization, and vector embedding indexing.",
    },
    {
        "name": "Athlete Analytics",
        "description": "Conversational intelligence, audience evaluation, and commercial fit analysis.",
    },
    {
        "name": "Athlete Management",
        "description": "Lifecycle management and administrative operations for athlete profiles.",
    },
]

app = FastAPI(
    title="HealthLete IQ API",
    description="Enterprise Sports Intelligence & Athlete Marketing Analytics API.",
    version="1.0.0",
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all API v1 endpoints
app.include_router(api_router)
