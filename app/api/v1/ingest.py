"""
ingest.py — Profile ingestion endpoint
"""

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException

from app.schemas.ingest import IngestResponse
from app.core.security import enforce_security
from app.services import cleaner
from app.services import ingestion

router = APIRouter(tags=["Athlete Ingestion"])


@router.post(
    "/ingest",
    response_model=IngestResponse,
    summary="Ingest and Index Athlete Profile",
    dependencies=[Depends(enforce_security)],
)
def ingest(payload: Dict[str, Any] = Body(..., description="Comprehensive athlete profile JSON data")):
    """
    Ingest, normalize, and semantically index an athlete profile dataset.

    Normalizes incoming profile attributes, generates contextual semantic chunks,
    calculates cryptographic content hashes to avoid redundant embedding calls,
    and updates the vector database.
    """
    try:
        text = cleaner.convert_json_to_text(payload)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Cleaning error: {e}")

    if not text.strip():
        raise HTTPException(
            status_code=422, detail="Cleaning produced empty text. Check the JSON.")

    try:
        athlete_id, profile_name = ingestion.extract_metadata(text)
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail="Could not read the athlete Id and Full Name from this JSON.")

    try:
        summary = ingestion.process_and_store_flattened_text(
            flattened_text=text,
            athlete_id=athlete_id,
            profile_name=profile_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding error: {e}")

    return IngestResponse(
        athlete_id=athlete_id,
        profile_name=profile_name,
        word_count=len(text.split()),
        **summary,
    )
