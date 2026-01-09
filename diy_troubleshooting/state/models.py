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

    def update_history(self, user_input: Optional[str], assistant_reply: str) -> None:
        """
        Append a user message and assistant reply to conversation history.

        Args:
            user_input: The user's message (omitted from history if None).
            assistant_reply: The assistant's response.
        """
        if user_input:
            self.history.append(Message(role="user", content=user_input))
        self.history.append(Message(role="assistant", content=assistant_reply))

    def advance_to_step(self, step_id: str) -> None:
        """
        Advance the active frame to a new step.

        Args:
            step_id: The step ID to advance to.

        Raises:
            ValueError: If there is no active frame.
        """
        current_frame = self.active_frame
        if not current_frame:
            raise ValueError("Cannot advance: no active frame.")
        current_frame.current_step_id = step_id

    def enter_workflow(self, workflow_name: str, start_step_id: str) -> None:
        """
        Push a new frame for a child workflow onto the stack.

        Args:
            workflow_name: The workflow identifier.
            start_step_id: The entry point step ID for the workflow.
        """
        child_frame = Frame(
            workflow_name=workflow_name,
            current_step_id=start_step_id,
        )
        self.stack.append(child_frame)

    def return_from_workflow(self, result: WorkflowResult) -> None:
        """
        Pop the current frame and deliver the result to the parent frame's mailbox.

        If a parent frame exists, the result is placed in its pending_child_result
        for processing on the next turn.

        Args:
            result: The workflow result to deliver to the parent.
        """
        self.stack.pop()
        if self.stack:
            self.stack[-1].pending_child_result = result