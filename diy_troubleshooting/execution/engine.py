"""
Engine - Workflow Orchestration Layer

The WorkflowEngine is the deterministic state machine ("The Manager") that
maintains process flow, manages the call stack, and delegates step
execution to the StepExecutor ("The Worker").

Response Strategy:
- HOLD (no transition): Return StepExecutor's StepDecision for current step
- Transition (ADVANCE/PUSH/POP): Return new current step's StepDecision,
  with a smooth transition message generated using the previous step's context

This avoids awkward concatenation of multiple independent LLM replies.
"""

import logging
from typing import Tuple, Optional

from ..state.models import SessionState, Frame, Message, WorkflowResult
from ..domain.models import Workflow, Step, WorkflowLink
from .schemas.decisions import StepStatus, StepDecision
from ..repositories.workflow import WorkflowRepository
from ..llm.interface import LLMProvider
from .executor import StepExecutor
from .schemas.state_machine import StateMachineTransition, TransitionMeta
from .transitions import introduce_step

logger = logging.getLogger(__name__)


class WorkflowEngine:
    def __init__(self, repository: WorkflowRepository, llm_provider: LLMProvider):
        self.repository = repository
        self.llm_provider = llm_provider

    async def handle_message(
        self, session: SessionState, user_input: str
    ) -> StepDecision:
        """
        The Orchestrator.

        Evaluates the current step, applies state transitions, and generates
        a response. For transitions (ADVANCE/PUSH/POP), uses introduce_step()
        to create a unified message instead of concatenating multiple replies.
        """
        if not session.active_frame:
            raise ValueError("Cannot handle message: session has no active workflow")

        # Delegate to StepExecutor: get LLM's assessment of user input against current step's goal
        frame, workflow, current_step = self._get_execution_context(session)
        decision = await self._execute_step(
            active_frame=frame,
            step_def=current_step,
            user_input=user_input,
            history=session.history,
        )

        # Apply decision to state machine
        # MUTATES: session.stack, frame.current_step_id
        fsm_transition = self._apply_decision(session, frame, workflow, decision)

        # Generate response
        is_holding = fsm_transition == StateMachineTransition.HOLD
        workflow_ended = not session.stack

        if is_holding or workflow_ended:
            return self._return_direct_response(session, user_input, decision)

        # Transitioned: return new step's StepDecision with smooth transition message
        return await self._generate_transition_response(
            session=session,
            previous_step=current_step,
            transition=fsm_transition,
            decision=decision,
            user_input=user_input,
        )

    # ==========================================================================
    # State Mutation & Translation (The Core Logic)
    # ==========================================================================

    def _apply_decision(
        self,
        session: SessionState,
        frame: Frame,
        workflow: Workflow,
        decision: StepDecision,
    ) -> StateMachineTransition:
        """
        Mutates the session state AND translates the StepDecision into a StateMachineTransition.
        """
        # Case 1: Hold State (Stay on Current Step)
        if decision.status == StepStatus.IN_PROGRESS:
            return StateMachineTransition.HOLD

        if decision.status == StepStatus.GIVE_UP:
            return StateMachineTransition.HOLD

        # Case 2: Advance to Next Step
        if decision.status == StepStatus.COMPLETE:
            return self._advance_or_pop(session, frame, workflow, decision)

        # Case 3: Branch to Child Workflow
        if decision.status == StepStatus.CALL_WORKFLOW:
            target_workflow_id = decision.result_value
            if not target_workflow_id:
                logger.warning("CALL_WORKFLOW status without target workflow ID")
                return StateMachineTransition.HOLD
            if not self._workflow_exists(target_workflow_id):
                logger.warning(f"CALL_WORKFLOW target not found: {target_workflow_id}")
                return StateMachineTransition.HOLD
            return self._push_child_workflow(session, target_workflow_id)

        # Fallback: Unknown status, hold state unchanged and wait for user's input
        logger.warning(f"Unknown StepStatus received: {decision.status}")
        return StateMachineTransition.HOLD

    def _advance_or_pop(
        self,
        session: SessionState,
        frame: Frame,
        workflow: Workflow,
        decision: StepDecision,
    ) -> StateMachineTransition:
        """
        Resolves the next step and advances to it, or pops the frame if workflow ends.
        """
        # Resolve Next Step ID
        current_step = workflow.steps[frame.current_step_id]
        next_step_id = None

        if current_step.type == "ask_choice" and current_step.options:
            selected_option = next(
                (
                    opt
                    for opt in current_step.options
                    if opt.id == decision.result_value
                ),
                None,
            )
            next_step_id = (
                selected_option.next_step_id
                if selected_option
                else current_step.next_step
            )
        else:
            next_step_id = current_step.next_step

        # Mutate State & Return FSM Transition Type
        next_step_def = workflow.steps[next_step_id]  # Fail fast if malformed
        if next_step_def.type == "end":
            return self._pop_frame(session, workflow, decision)

        frame.current_step_id = next_step_id
        return StateMachineTransition.ADVANCE

    def _pop_frame(
        self,
        session: SessionState,
        completed_workflow: Workflow,
        final_decision: StepDecision,
    ) -> StateMachineTransition:
        """
        Pops the current frame. If a parent frame exists, delivers the result to its mailbox.
        """
        session.stack.pop()

        # If there's a parent frame waiting, deliver the child's result
        if session.stack:
            parent_frame = session.stack[-1]
            parent_frame.pending_child_result = WorkflowResult(
                source_workflow_id=completed_workflow.name,
                status="SUCCESS",
                summary=final_decision.reply_to_user,
                slots_collected={},  # Slots are session-wide, not frame-specific
            )
            logger.info(f"Child workflow '{completed_workflow.name}' completed, result delivered to parent")

        return StateMachineTransition.POP

    def _push_child_workflow(
        self,
        session: SessionState,
        target_workflow_id: str,
    ) -> StateMachineTransition:
        """
        Pushes a new frame for the child workflow onto the stack.
        """
        target_workflow = self.repository.get_workflow(target_workflow_id)
        child_frame = Frame(
            workflow_name=target_workflow_id,
            current_step_id=target_workflow.start_step,
        )
        session.stack.append(child_frame)
        logger.info(f"Pushed child workflow: {target_workflow_id}")

        return StateMachineTransition.PUSH

    # ==========================================================================
    # Response Generation
    # ==========================================================================

    def _return_direct_response(
        self,
        session: SessionState,
        user_input: str,
        decision: StepDecision,
    ) -> StepDecision:
        """Return executor's reply directly when staying on the current step."""
        if session.active_frame:
            session.active_frame.pending_child_result = None
        self._update_history(session, user_input, decision.reply_to_user)
        return decision

    async def _generate_transition_response(
        self,
        session: SessionState,
        previous_step: Step,
        transition: StateMachineTransition,
        decision: StepDecision,
        user_input: str,
    ) -> StepDecision:
        """
        Produce a StepDecision for the new current step after a transition.

        Uses context from the previous step to generate a smooth transition message.
        """
        # Re-fetch context—now pointing to the NEW step after mutation
        new_frame, _, next_step = self._get_execution_context(session)

        meta = TransitionMeta(
            transition_type=transition,
            reasoning=decision.reasoning,
            workflow_link=self._find_workflow_link(previous_step, decision.result_value),
            child_result=new_frame.pending_child_result,
        )

        intro_decision = await introduce_step(
            llm=self.llm_provider,
            from_step=previous_step,
            to_step=next_step,
            meta=meta,
            history=session.history,
            user_input=user_input,
        )

        new_frame.pending_child_result = None
        self._update_history(session, user_input, intro_decision.reply_to_user)
        return intro_decision

    # ==========================================================================
    # Standard Helpers
    # ==========================================================================

    def _get_execution_context(
        self, session: SessionState
    ) -> Tuple[Frame, Workflow, Step]:
        active_frame = session.active_frame
        if not active_frame:
            raise ValueError("Session stack is empty.")
        workflow_def = self.repository.get_workflow(active_frame.workflow_name)
        step_def = workflow_def.steps[active_frame.current_step_id]
        return active_frame, workflow_def, step_def

    def _workflow_exists(self, workflow_id: str) -> bool:
        try:
            self.repository.get_workflow(workflow_id)
            return True
        except Exception:
            return False

    async def _execute_step(
        self,
        active_frame: Frame,
        step_def: Step,
        user_input: Optional[str],
        history: list[Message],
    ) -> StepDecision:
        executor = StepExecutor(self.llm_provider)
        return await executor.run_turn(
            step=step_def, frame=active_frame, user_input=user_input, history=history
        )

    def _update_history(
        self, session: SessionState, user_input: Optional[str], reply: str
    ):
        """Append user input and assistant reply to conversation history."""
        if user_input:
            session.history.append(Message(role="user", content=user_input))
        session.history.append(Message(role="assistant", content=reply))

    def _find_workflow_link(
        self, step: Step, target_workflow_id: Optional[str]
    ) -> Optional[WorkflowLink]:
        """Find the WorkflowLink that matches the target workflow ID."""
        if not target_workflow_id or not step.suggested_links:
            return None
        return next(
            (link for link in step.suggested_links if link.target_workflow_id == target_workflow_id),
            None,
        )
