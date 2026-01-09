"""
State Layer - Runtime Data Models

This module defines the runtime state model that tracks the user's journey
through troubleshooting workflows. It implements a Call Stack pattern to
support nested workflows (sub-routines) and maintains session-wide data slots.
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class WorkflowResult(BaseModel):
    """
    Represents the output of a completed sub-workflow.
    """
    source_workflow_id: str
    status: Literal["SUCCESS", "ABORTED"]
    summary: str
    slots_collected: Dict[str, Any] = Field(default_factory=dict)


class Frame(BaseModel):
    """
    Represents a single item on the call stack.
    """
    workflow_name: str
    current_step_id: str
    
    # Holds the result from a completed child workflow until the parent processes it.
    pending_child_result: Optional[WorkflowResult] = None


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class SessionState(BaseModel):
    """
    The global state for a single user session.
    """
    session_id: str
    stack: List[Frame] = Field(default_factory=list)
    slots: Dict[str, Any] = Field(default_factory=dict)
    history: List[Message] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def active_frame(self) -> Optional[Frame]:
        if not self.stack:
            return None
        return self.stack[-1]