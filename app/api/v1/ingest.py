from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException

from app.schemas.ingest import IngestResponse
from app.core.security import enforce_security
from app.core.config import CHAT_API_KEY
from app.services import cleaner
from app.services import ingestion
from app.services.payload_decoder import decode_payload

router = APIRouter(tags=["Athlete Ingestion"])


def _process_athlete_payload(payload: Dict[str, Any]) -> IngestResponse:
    """Core pipeline: clean json, extract metadata, and index in vector database."""
    try:
        text = cleaner.convert_json_to_text(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleaning error: {e}")

    if not text.strip():
        raise HTTPException(status_code=422, detail="Cleaning produced empty text. Check the JSON.")

    try:
        athlete_id, profile_name = ingestion.extract_metadata(text)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="Could not read the athlete Id and Full Name from this JSON.",
        )

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


@router.post(
    "/ingest",
    response_model=IngestResponse,
    summary="Ingest and Index Athlete Profile",
    dependencies=[Depends(enforce_security)],
)
def ingest(payload: Dict[str, Any] = Body(..., description="Athlete profile JSON, or compressed wrapper")):
    """
    Ingest, normalize, and semantically index an athlete profile dataset.
    Supports:
    1. Standard raw JSON.
    2. Base64 / gzip-compressed payload: {"compressed": true, "payload": "..."}
    """
    resolved_payload = decode_payload(payload, secret_key=CHAT_API_KEY)
    return _process_athlete_payload(resolved_payload)

