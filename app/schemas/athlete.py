"""
athlete.py — Request and Response models for athlete management endpoints
"""

from typing import Optional

from pydantic import BaseModel, Field


class DeleteResponse(BaseModel):
    success: bool = Field(True, description="Indicates whether deletion completed successfully")
    athlete_id: str = Field(..., description="Unique athlete identifier (UUID)")
    profile_name: Optional[str] = Field(None, description="Athlete full name")
    deleted_chunks: int = Field(..., description="Total vector chunks removed")
    message: str = Field(..., description="Operation summary message")
