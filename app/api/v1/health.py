"""
health.py — System health endpoints
"""

from fastapi import APIRouter

router = APIRouter(tags=["System"])


@router.get("/health", summary="System Health Check")
def health_check():
    """Returns the service health status and current operational metrics."""
    return {"status": "ok", "app": "HealthLete IQ API", "version": "1.0.0"}
