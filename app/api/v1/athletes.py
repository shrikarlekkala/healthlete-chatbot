"""
athletes.py — Athlete management endpoints
"""

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.athlete import DeleteResponse
from app.core.security import enforce_security
from app.services import ingestion
from app.api.v1.chat import clean_id

router = APIRouter(tags=["Athlete Management"])


@router.delete(
    "/athlete/{athlete_id}",
    response_model=DeleteResponse,
    summary="Delete Athlete Profile",
    dependencies=[Depends(enforce_security)],
)
def delete_athlete(athlete_id: str):
    """
    Remove an athlete profile and all associated vector embeddings from the knowledge store.
    """
    athlete_id = clean_id(athlete_id)

    try:
        result = ingestion.delete_athlete(athlete_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete error: {e}")

    if not result.get("deleted"):
        raise HTTPException(
            status_code=404, detail=f"No data found for athlete '{athlete_id}'.")

    return DeleteResponse(
        athlete_id=athlete_id,
        profile_name=result.get("profile_name"),
        deleted_chunks=result.get("deleted_chunks"),
        message=f"Athlete '{result.get('profile_name')}' and all embeddings deleted.",
    )
