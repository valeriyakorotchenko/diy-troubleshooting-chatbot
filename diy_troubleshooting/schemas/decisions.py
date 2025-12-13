"""
Schemas - Structured Output Models for LLM Responses

This module defines Pydantic models used for structured LLM outputs.
These schemas enforce strict JSON formatting on LLM responses, ensuring
predictable and parseable results from the StepExecutor.
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class StepStatus(str, Enum):
    """
    The distinct states a Step can result in after a turn.
    """
    IN_PROGRESS = "IN_PROGRESS"       # Goal not met, keep chatting
    COMPLETE = "COMPLETE"             # Goal met, move to next step
    CALL_WORKFLOW = "CALL_WORKFLOW"   # User agreed to branch to child workflow
    GIVE_UP = "GIVE_UP"               # Escalate to human

class StepDecision(BaseModel):
    """
    The strict JSON structure the LLM must generate for every turn.
    Named "StepDecision" because this represents the result of StepExecutor making a decision about the current Step status.
    """
    reply_to_user: str = Field(
        ..., 
        description="The natural language response to show the user. Be helpful, clear, and safe."
    )
    status: StepStatus = Field(
        ..., 
        description="The status of the current step after this turn."
    )
    result_value: Optional[str] = Field(
        None, 
        description="The value extracted (for slots), the Option ID (for choices), or the Workflow ID (for branching)."
    )
    reasoning: str = Field(
        ..., 
        description="Brief internal chain-of-thought justifying why this status was chosen."
    )