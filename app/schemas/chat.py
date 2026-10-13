"""
chat.py — Request and Response models for the /chat endpoint
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., description="Message author role: 'user' or 'assistant'")
    content: str = Field(..., description="Message text content")


class ChatRequest(BaseModel):
    athlete_id: str = Field(..., description="Unique athlete identifier (UUID)")
    message: str = Field(..., description="User question or marketing analysis inquiry")
    chat_history: List[ChatMessage] = Field(
        default_factory=list,
        description="Historical messages in the current session for multi-turn conversational context",
    )


class ChatResponse(BaseModel):
    success: bool = Field(True, description="Indicates request success status")
    athlete_id: str = Field(..., description="Unique athlete identifier (UUID)")
    profile_name: Optional[str] = Field(None, description="Resolved athlete full name")
    answer: str = Field(..., description="Analyst evaluation and strategic recommendations")
    path: str = Field(
        ..., description="Resolution path: profile | web_search | profile_only | off_topic"
    )
    decision: str = Field(
        ..., description="Routing classification: PROFILE | INSUFFICIENT | OFF_TOPIC"
    )
    chat_history: List[ChatMessage] = Field(..., description="Updated conversational history for next turn")
