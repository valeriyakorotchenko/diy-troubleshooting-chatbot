"""
Prompt building for step introductions after transitions.

Templates and assembly logic for generating unified messages when
the engine transitions between steps (ADVANCE, PUSH, POP).
"""

from ...domain.models import Step
from ..schemas.state_machine import TransitionMeta, StateMachineTransition

# =============================================================================
# TEMPLATES
# =============================================================================

TRANSITION_PROMPT = """You are an expert DIY Home Repair Assistant introducing the next step.

Your task is to generate a response that:
1. Briefly acknowledges what just happened (the transition)
2. Smoothly introduces the current step the user needs to complete
3. Includes any safety warnings with appropriate emphasis

Keep the message concise but warm. Avoid redundancy.

{transition_context}

STEP TO INTRODUCE:
Goal: {to_step_goal}
{step_details}

OUTPUT INSTRUCTIONS:
- reply_to_user: Your natural, flowing message to the user
- status: Must be "IN_PROGRESS" (the user hasn't started this step yet)
- reasoning: Brief explanation of the transition (e.g., "Introduced step after completing previous")
- result_value: Leave empty (null)"""

CONTEXT_ADVANCE = """TRANSITION: Step completed, advancing to next step.
Completed step goal: {from_step_goal}
Why it's complete: {reasoning}"""

CONTEXT_PUSH = """TRANSITION: Branching to helper sub-workflow.
Parent step: {from_step_goal}
Sub-workflow: {workflow_title}
Rationale: {workflow_rationale}"""

CONTEXT_POP = """TRANSITION: Sub-workflow completed, returning to main task.
Completed: {child_workflow_id}
Summary: {child_summary}"""

STEP_CONTEXT = "Context: {context}"
STEP_WARNING = "SAFETY WARNING: {warning}"
STEP_WARNING_INSTRUCTION = "You MUST include this warning prominently in your message."


# =============================================================================
# BUILDER FUNCTIONS
# =============================================================================

def build_step_introduction_prompt(from_step: Step, to_step: Step, meta: TransitionMeta) -> str:
    """Build the system prompt for step introduction after transition."""
    return TRANSITION_PROMPT.format(
        transition_context=_build_transition_context(from_step, meta),
        to_step_goal=to_step.goal,
        step_details=_build_step_details(to_step),
    )


def _build_transition_context(from_step: Step, meta: TransitionMeta) -> str:
    """Select and fill the appropriate transition context block."""
    match meta.transition_type:
        case StateMachineTransition.ADVANCE:
            return CONTEXT_ADVANCE.format(
                from_step_goal=from_step.goal,
                reasoning=meta.reasoning,
            )
        case StateMachineTransition.PUSH:
            return CONTEXT_PUSH.format(
                from_step_goal=from_step.goal,
                workflow_title=meta.workflow_link.title if meta.workflow_link else "sub-workflow",
                workflow_rationale=meta.workflow_link.rationale if meta.workflow_link else "",
            )
        case StateMachineTransition.POP:
            if not meta.child_result:
                raise ValueError("POP transition requires child_result")
            return CONTEXT_POP.format(
                child_workflow_id=meta.child_result.source_workflow_id,
                child_summary=meta.child_result.summary,
            )


def _build_step_details(step: Step) -> str:
    """Build optional step details (context + warning)."""
    parts = filter(None, [
        STEP_CONTEXT.format(context=step.background_context) if step.background_context else None,
        STEP_WARNING.format(warning=step.warning) if step.warning else None,
        STEP_WARNING_INSTRUCTION if step.warning else None,
    ])
    return "\n".join(parts)
