"""
Transition Types - FSM State Transition Definitions

Type definitions for workflow state machine transitions.
Used by both the engine (to classify transitions) and the executor (to compose messages).
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from ...domain.models import WorkflowLink
from ...state.models import WorkflowResult


class StateMachineTransition(Enum):
    """
    Strict State Machine terminology describing what happened to the graph pointers.
    This decouples the Engine logic from the LLM's 'StepStatus' - an LLM's assessment
    of goal completion for the current step.
    """

    HOLD = auto()  # Pointer remains on current node
    ADVANCE = auto()  # Pointer moved to the next linear or branched node
    PUSH = auto()  # Child workflow frame pushed onto stack
    POP = auto()  # Frame popped (workflow completed)


@dataclass
class TransitionMeta:
    """
    Metadata about a transition (without the steps themselves).

    Steps are passed explicitly to introduce_step(); this bundles the rest.
    """

    transition_type: StateMachineTransition
    reasoning: str
    workflow_link: Optional[WorkflowLink] = None
    child_result: Optional[WorkflowResult] = None
