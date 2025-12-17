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
    Represents the LLM's assessment of goal completion for the current step.
    It answers a single question: "Based on the user's latest input, has the specific goal defined in this step been satisfied?"

    IN_PROGRESS: The goal is not yet met; more interaction is needed.
    COMPLETE: The goal is fully satisfied.
    GIVE_UP: The goal cannot be met due to a blocker or safety issue.
    """
    IN_PROGRESS = "IN_PROGRESS"       
    COMPLETE = "COMPLETE"             
    CALL_WORKFLOW = "CALL_WORKFLOW"  
    GIVE_UP = "GIVE_UP"          

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