"""
ingest.py — Request and Response models for the /ingest endpoint
"""

from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    success: bool = Field(True, description="Indicates whether the ingestion completed successfully")
    athlete_id: str = Field(..., description="Unique athlete identifier (UUID)")
    profile_name: str = Field(..., description="Resolved athlete full name")
    word_count: int = Field(..., description="Total word count of cleaned profile representation")
    total_chunks: int = Field(..., description="Total semantic chunks processed")
    skipped_unchanged: int = Field(..., description="Count of unchanged chunks skipped via hash verification")
    inserted_new: int = Field(..., description="Count of new chunks embedded and stored")
    updated_changed: int = Field(..., description="Count of modified chunks re-embedded")
    deleted_orphans: int = Field(..., description="Count of obsolete orphaned chunks removed")
