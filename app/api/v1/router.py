"""
router.py — Main v1 API router aggregation
"""

from fastapi import APIRouter

from app.api.v1 import health
from app.api.v1 import ingest
from app.api.v1 import chat
from app.api.v1 import athletes

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(ingest.router)
api_router.include_router(chat.router)
api_router.include_router(athletes.router)
