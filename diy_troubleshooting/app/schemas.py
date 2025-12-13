"""
API Layer - Request/Response Schemas

Pydantic models for API request and response validation.
"""

from typing import Optional, Any

from pydantic import BaseModel


class CreateSessionResponse(BaseModel):
    session_id: str


class UserMessage(BaseModel):
    text: str


class DebugInfo(BaseModel):
    """Debug information for troubleshooting the chatbot itself."""
    active_frame: Optional[dict[str, Any]] = None
    current_step: Optional[dict[str, Any]] = None
    message_history: Optional[list[dict[str, Any]]] = None


class ChatResponse(BaseModel):
    reply: str
    status: str
    debug: Optional[DebugInfo] = None
