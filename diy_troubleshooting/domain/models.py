"""
Domain Layer - Static Data Models

This module defines the core domain model representing the static structure
of troubleshooting guides. These classes are derived from source content
(HTML guides) and define Workflows, Steps, and Links.

-----------------------------------------------
We use Pydantic here despite the DDD convention of keeping domain models
framework-agnostic. This is a pragmatic tradeoff justified by:

1. These models are structural definitions, not rich domain entities. They
   contain no business logic — it lives in WorkflowEngine and StepExecutor.
2. Pydantic's recursive parsing converts deeply nested JSON from the database
   into validated Python objects in one line (Workflow → Step → Option/Media).
3. Validation at deserialization catches malformed data at the infrastructure
   boundary rather than at runtime when a user hits a broken step.

Tradeoff: This couples the domain layer to Pydantic. If these models later
require complex domain behavior, consider extracting a separate DTO layer.
"""

from enum import StrEnum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class StepType(StrEnum):
    """
    Classifies step behavior in a workflow.

    Values:
    - INSTRUCTION: Guidance without user choice
    - ASK_CHOICE: Decision point with predefined options
    - ASK_SLOT: Collects specific data from user
    - RESPOND: Provides contextual information
    - END: Terminal step marking workflow completion
    - CALL_WORKFLOW: Triggers a nested sub-workflow
    """

    INSTRUCTION = "instruction"
    ASK_CHOICE = "ask_choice"
    ASK_SLOT = "ask_slot"
    RESPOND = "respond"
    END = "end"
    CALL_WORKFLOW = "call_workflow"


class Media(BaseModel):
    """
    Visual aids extracted from source content.

    Attributes:
        url: Source URL of the image.
        caption: Descriptive text explaining the image. Used by StepExecutor
            to refer to this image in the chat.
    """
    url: str
    caption: str


class WorkflowLink(BaseModel):
    """
    Potential branch to another workflow (the "Smart Link").

    Enables dynamic branching to recursive sub-workflows (e.g., "Drain Water
    Heater" inside "Fix Lukewarm Water"). Unlike Options (which advance the
    workflow), Smart Links are helper workflows for completing the current step.

    Attributes:
        target_workflow_id: Destination workflow ID (pushed onto call stack).
        title: Human-readable title (e.g., "How to Drain a Water Heater").
        rationale: Why this detour may be needed. StepExecutor uses this
            to determine when to offer the link.
        trigger_keywords: Keywords indicating user intent to take this path.
    """
    target_workflow_id: str
    title: str
    rationale: str
    trigger_keywords: List[str] = Field(default_factory=list)


class Option(BaseModel):
    """
    Logical outcome for a step (used when StepType is ask_choice).

    Represents a valid "exit" for a step, driving internal workflow branching
    (e.g., Fixed vs. Not Fixed). Included in System Prompt to inform LLM
    of valid result_value choices when marking the step COMPLETE.

    Attributes:
        id: State key used as result_value (e.g., "outcome_fixed").
        label: Human-readable description (e.g., "Adjusted and fixed").
        next_step_id: Step to transition to if this outcome selected.
    """
    id: str
    label: str
    next_step_id: str


class Step(BaseModel):
    """
    Fundamental unit of work in a troubleshooting workflow.

    Contains instructions for the StepExecutor (Agent). Defines a goal,
    supporting context, and transitions the LLM uses to guide users through
    a single troubleshooting step.

    StepExecutor dynamically constructs System Prompt from these fields,
    conditionally injecting blocks based on which fields are present.

    Attributes:
        id: Unique identifier within the workflow.
        type: StepType
        goal: Step objective / success criteria. Becomes Core Block in system prompt
        background_context: Static facts/tips injected into Core Block
        media: Media object - visual aid for the step
        warning: Critical safety text. Triggers addition of Safety Block in system prompt if present
        suggested_links: Available WorkflowLinks - turned into Helper Workflow Block in the system prompt
        options: Valid logical exits for ask_choice - turned into Outcome Block in system prompt
        next_step: Default subsequent step ID (when no Option selected).
        slot_name: Field name for storing collected data (for ask_slot).
    """
    id: str
    type: StepType
    goal: str
    background_context: Optional[str] = None
    media: Optional[Media] = None
    warning: Optional[str] = None
    suggested_links: List[WorkflowLink] = Field(default_factory=list)
    options: List[Option] = Field(default_factory=list)
    next_step: Optional[str] = None
    slot_name: Optional[str] = None


class Workflow(BaseModel):
    """
    Sequence of steps forming a complete troubleshooting guide.

    Top-level organizational unit. Can be invoked directly (root) or via
    WorkflowLinks (nested sub-workflow). When called, WorkflowEngine creates
    a new Frame on the stack initialized with start_step.

    Attributes:
        name: Unique identifier (also used as target_workflow_id in links).
        start_step: Entry point step ID.
        steps: Dict mapping Step IDs to Step objects (O(1) lookup).
    """
    name: str
    start_step: str
    steps: Dict[str, Step] = Field(default_factory=dict)
    title: Optional[str] = None


