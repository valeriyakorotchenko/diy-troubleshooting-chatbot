"""
Transition Step Introduction.

Produces a StepDecision for the new step after a transition (ADVANCE, PUSH, POP).
The LLM generates a unified message that acknowledges the transition and
introduces the next step.
"""

import logging
from typing import List

from ..domain.models import Step
from ..llm.interface import LLMProvider
from ..state.models import Message
from .prompts import Template, render
from .schemas.decisions import StepDecision, StepStatus
from .schemas.state_machine import TransitionMeta

logger = logging.getLogger(__name__)


async def introduce_step(
    llm: LLMProvider,
    from_step: Step,
    to_step: Step,
    meta: TransitionMeta,
    history: List[Message],
    user_input: str,
) -> StepDecision:
    """
    Produce a StepDecision that introduces the next step after a transition.

    Uses context from the completed step (from_step) and transition metadata
    to generate a smooth message that acknowledges what happened and naturally
    introduces the new step (to_step).

    Args:
        llm: The LLM provider to use for generation
        from_step: The step we're transitioning from (provides context for acknowledgment)
        to_step: The step we're transitioning to (being introduced)
        meta: Transition metadata (type, reasoning, workflow_link, child_result)
        history: Conversation history for tone/context
        user_input: The user's input that triggered this transition

    Returns:
        StepDecision for to_step with IN_PROGRESS status.
    """
    system_prompt = render(
        Template.STEP_INTRODUCTION,
        from_step=from_step,
        to_step=to_step,
        meta=meta,
    )

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    if user_input:
        messages.append({"role": "user", "content": user_input})

    try:
        return await llm.generate_structured_output(
            messages=messages,
            response_model=StepDecision,
        )

    except Exception as e:
        logger.error(f"Step introduction failed: {e}")
        return StepDecision(
            reply_to_user=f"Let's proceed. {to_step.goal}",
            status=StepStatus.IN_PROGRESS,
            reasoning=f"Error during introduction: {str(e)}",
        )
