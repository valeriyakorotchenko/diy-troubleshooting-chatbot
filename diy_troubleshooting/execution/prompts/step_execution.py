"""
Prompt building for step execution.

Templates and assembly logic for executing a conversational turn within a step.
The LLM helps the user work toward the step's goal, provides guidance,
and determines when the goal has been achieved.
"""

from ...domain.models import Step
from ...state.models import Frame

# =============================================================================
# TEMPLATES
# =============================================================================

STEP_TURN_PROMPT = """You are an expert DIY Home Repair Assistant.
You are guiding a user through a specific troubleshooting step.

CURRENT STEP GOAL: {goal}
CONTEXT: {context}
{warning_block}
{mailbox_block}
INSTRUCTIONS:
1. If the user has satisfied the Goal (or confirmed the action), set status='COMPLETE'.
2. If the user is struggling or asks for help, provide guidance based on the Context.
3. If the user encounters a danger or cannot perform the step, set status='GIVE_UP'.
{options_block}
{workflow_links_block}"""

WARNING_BLOCK = """CRITICAL SAFETY WARNING: {warning}
You MUST ensure the user acknowledges this warning before proceeding.
"""

MAILBOX_BLOCK = """SYSTEM NOTIFICATION: A sub-task has just finished.
Sub-task Status: {status}
Sub-task Summary: {summary}
INSTRUCTION: Welcome the user back. Use this result to determine if the current step goal is now met.
"""

OPTIONS_BLOCK = """
VALID OUTCOMES (for 'result_value' when COMPLETE):
{options}
When status is COMPLETE, you MUST set 'result_value' to one of the IDs above."""

OPTION_LINE = "- ID: '{id}' | Description: {label}"

WORKFLOW_LINKS_BLOCK = """
AVAILABLE HELPER WORKFLOWS:
If the user explicitly asks for help with a related sub-task, you can branch to one of these workflows.
{links}
To branch to a helper workflow:
- Set status='CALL_WORKFLOW'
- Set result_value to the workflow ID
IMPORTANT: Only use CALL_WORKFLOW when the user clearly needs or requests the sub-task. Do not proactively suggest branching unless the user is stuck."""

WORKFLOW_LINK_LINE = "- ID: '{id}' | Title: {title}\n  When to offer: {rationale}"


# =============================================================================
# BUILDER FUNCTIONS
# =============================================================================

def build_step_execution_prompt(step: Step, frame: Frame) -> str:
    """
    Build the system prompt for executing a step turn.

    The resulting prompt instructs the LLM to help the user work toward
    the step's goal and generate an appropriate response.
    """
    return STEP_TURN_PROMPT.format(
        goal=step.goal,
        context=step.background_context,
        warning_block=_build_warning_block(step),
        mailbox_block=_build_mailbox_block(frame),
        options_block=_build_options_block(step),
        workflow_links_block=_build_workflow_links_block(step),
    )


def _build_warning_block(step: Step) -> str:
    """Build the safety warning block if the step has a warning."""
    if not step.warning:
        return ""
    return WARNING_BLOCK.format(warning=step.warning)


def _build_mailbox_block(frame: Frame) -> str:
    """Build the child workflow result notification if a child just completed."""
    if not frame.pending_child_result:
        return ""
    result = frame.pending_child_result
    return MAILBOX_BLOCK.format(
        status=result.status,
        summary=result.summary,
    )


def _build_options_block(step: Step) -> str:
    """Build the valid outcomes block for ask_choice steps."""
    if step.type != "ask_choice" or not step.options:
        return ""
    option_lines = [
        OPTION_LINE.format(id=opt.id, label=opt.label)
        for opt in step.options
    ]
    return OPTIONS_BLOCK.format(options="\n".join(option_lines))


def _build_workflow_links_block(step: Step) -> str:
    """Build the helper workflows block if the step has suggested links."""
    if not step.suggested_links:
        return ""
    link_lines = [
        WORKFLOW_LINK_LINE.format(
            id=link.target_workflow_id,
            title=link.title,
            rationale=link.rationale,
        )
        for link in step.suggested_links
    ]
    return WORKFLOW_LINKS_BLOCK.format(links="\n".join(link_lines))
