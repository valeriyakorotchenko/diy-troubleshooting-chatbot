"""
API Layer - Request/Response Schemas
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel

# --- Input schemas for API requests. ---

class UserMessage(BaseModel):
    """
    Payload for sending a new message (Input).
    We only ask for text; the 'user' role is implied.
    """
    text: str


# --- Output schemas for API responses. ---

class CreateSessionResponse(BaseModel):
    session_id: str

class ChatMessage(BaseModel):
    """
    Represents a single turn in the conversation history (Output).
    Includes the 'role' to distinguish between user and assistant.
    """
    role: Literal["user", "assistant"]
    content: str

class DebugInfo(BaseModel):
    active_frame: Optional[dict[str, Any]] = None
    current_step: Optional[dict[str, Any]] = None
    message_history: Optional[list[dict[str, Any]]] = None

class ChatResponse(BaseModel):
    """The immediate response after a user interaction."""
    reply: str
    status: str
    debug: Optional[DebugInfo] = None

class SessionRead(BaseModel):
    """The full resource representation of a Session."""
    session_id: str
    status: Literal["IN_PROGRESS", "COMPLETED"]
    history: List[ChatMessage]  
    current_workflow: Optional[str] = None
    updated_at: Optional[datetime] = None

    debug: Optional[Dict[str, Any]] = None