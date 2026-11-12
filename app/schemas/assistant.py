"""
assistant.py - Request and response models for the brand assistant.

The NestJS backend owns all brand data. It asks /assistant/plan which tools
to run, runs them itself, then sends the results to /assistant/answer/stream.
"""

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field

from app.schemas.chat import ChatMessage


class AssistantCatalog(BaseModel):
    conditions: List[str] = Field(
        default_factory=list, max_length=1000, description="Health condition names in the catalog"
    )
    sports: List[str] = Field(
        default_factory=list, max_length=500, description="Sport names in the catalog"
    )
    brand_conditions: List[str] = Field(
        default_factory=list,
        max_length=200,
        description="Health conditions this brand selected at registration",
    )


class AssistantPlanRequest(BaseModel):
    message: str = Field(..., max_length=500)
    chat_history: List[ChatMessage] = Field(default_factory=list, max_length=20)
    catalog: AssistantCatalog = Field(default_factory=AssistantCatalog)


class AssistantToolCall(BaseModel):
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class AssistantPlanResponse(BaseModel):
    success: bool = True
    tool_calls: List[AssistantToolCall]


class AssistantToolResult(BaseModel):
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    result: Any = None


class AssistantAnswerRequest(BaseModel):
    message: str = Field(..., max_length=500)
    chat_history: List[ChatMessage] = Field(default_factory=list, max_length=20)
    surface: Literal["assistant", "discover"] = "assistant"
    tool_results: List[AssistantToolResult] = Field(default_factory=list, max_length=6)
