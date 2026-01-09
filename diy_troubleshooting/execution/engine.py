"""
Engine - Workflow Orchestration Layer

The WorkflowEngine is the deterministic state machine ("The Manager") that
maintains process flow, manages the call stack, and delegates step
execution to the StepExecutor ("The Worker").

Response Strategy:
- HOLD or workflow ended: Return StepExecutor's decision as-is
- Transition (ADVANCE/PUSH/POP): Generate a new decision with a smooth
  transition message bridging the previous step to the new step

This avoids awkward concatenation of multiple independent LLM replies.
"""

import logging
from typing import Optional, Tuple

from ..domain.models import Step, StepType, Workflow, WorkflowLink
from ..llm.interface import LLMProvider
from ..repositories.workflow import WorkflowRepository
from ..state.models import Frame, Message, SessionState, WorkflowResult
from .executor import StepExecutor
from .schemas.decisions import StepDecision, StepStatus
from .schemas.state_machine import StateMachineTransition, TransitionMeta
from .transitions import introduce_step

logger = logging.getLogger(__name__)


class WorkflowEngine:
    def __init__(self, workflow_repository: WorkflowRepository, llm_provider: LLMProvider):
        self._workflow_repository = workflow_repository
        self._llm_provider = llm_provider

    async def handle_message(
        self, session: SessionState, user_input: str
    ) -> StepDecision:
        """
        The Orchestrator.

        Evaluates the current step, applies state transitions, and generates
        a response. For transitions (ADVANCE/PUSH/POP), uses introduce_step()
        to create a unified, coherent message instead of concatenating multiple replies.
        """
        if not session.active_frame:
            raise ValueError("Cannot handle message: session has no active workflow")

        # Load the execution context for the current session.
        frame, workflow, current_step = self._get_execution_context(session)

        # Delegate to StepExecutor to get the LLM's assessment of user input against the current step's goal.
        decision = await self._execute_step(
            active_frame=frame,
            step_def=current_step,
            user_input=user_input,
            history=session.history,
        )

        # Apply the decision to the state machine. This mutates session.stack and frame.current_step_id.
        fsm_transition = self._apply_decision(session, frame, workflow, decision)

        # Clear the child result mailbox now that we've processed it.
        if session.active_frame:
            session.active_frame.pending_child_result = None

        # Determine the final decision to return.
        is_holding = fsm_transition == StateMachineTransition.HOLD
        root_workflow_ended = not session.stack

        if is_holding or root_workflow_ended:
            # We are staying on the current step or the session has ended.
            final_decision = decision
        else:
            # We transitioned to a new step or workflow. Generate a coherent message that
            # acknowledges the previous step and introduces the new one, avoiding
            # awkward concatenation of two independent LLM replies.
            final_decision = await self._generate_transition_decision(
                session=session,
                previous_step=current_step,
                transition=fsm_transition,
                decision=decision,
                user_input=user_input,
            )

        self._update_history(session, user_input, final_decision.reply_to_user)
        return final_decision

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
        Apply a StepDecision to the session state and return the transition type.

        Mutates session state based on the decision:
        - HOLD: No mutation
        - ADVANCE: Updates frame.current_step_id
        - PUSH: Appends new Frame to session.stack
        - POP: Removes Frame from session.stack, delivers result to parent
        """
        # Hold on the current step without any state mutation.
        if decision.status in (StepStatus.IN_PROGRESS, StepStatus.GIVE_UP):
            return StateMachineTransition.HOLD

        # Check if the current step is an END step to pop, otherwise advance to the next step.
        if decision.status == StepStatus.COMPLETE:
            current_step = workflow.steps[frame.current_step_id]

            # If the current step is END, the workflow is complete. Pop the frame.
            if current_step.type == StepType.END:
                self._pop_frame(session, workflow, decision)
                return StateMachineTransition.POP

            # Otherwise, resolve and advance to the next step.
            next_step_id = self._resolve_next_step_id(current_step, decision)

            if next_step_id is None:
                raise ValueError(
                    f"Step '{current_step.id}' has no next_step defined and no matching option "
                    f"for result_value '{decision.result_value}'"
                )
            if next_step_id not in workflow.steps:
                raise ValueError(
                    f"Step '{current_step.id}' references non-existent next step '{next_step_id}'"
                )

            frame.current_step_id = next_step_id
            return StateMachineTransition.ADVANCE

        # Validate and push the child workflow onto the stack.
        if decision.status == StepStatus.CALL_WORKFLOW:
            target_workflow_id = decision.result_value
            if not target_workflow_id:
                logger.warning("CALL_WORKFLOW status without target workflow ID")
                return StateMachineTransition.HOLD
            if not self._workflow_exists(target_workflow_id):
                logger.warning(f"CALL_WORKFLOW target not found: {target_workflow_id}")
                return StateMachineTransition.HOLD

            self._push_child_workflow(session, target_workflow_id)
            return StateMachineTransition.PUSH

        # Unknown status received. Log a warning and hold.
        logger.warning(f"Unknown StepStatus received: {decision.status}")
        return StateMachineTransition.HOLD

    def _resolve_next_step_id(
        self, current_step: Step, decision: StepDecision
    ) -> Optional[str]:
        """
        Determine the next step ID based on step type and decision.

        For 'ask_choice' steps, uses the selected option's next_step_id.
        For other steps, uses the step's default next_step.
        """
        if current_step.type == "ask_choice" and current_step.options:
            selected_option = next(
                (opt for opt in current_step.options if opt.id == decision.result_value),
                None,
            )
            if selected_option:
                return selected_option.next_step_id
            # Fall through to the default next_step if no option matched.

        return current_step.next_step

    def _pop_frame(
        self,
        session: SessionState,
        completed_workflow: Workflow,
        final_decision: StepDecision,
    ) -> None:
        """
        Pop the current frame. If a parent frame exists, deliver the result to its mailbox.
        """
        session.stack.pop()

        if session.stack:
            parent_frame = session.stack[-1]
            parent_frame.pending_child_result = WorkflowResult(
                source_workflow_id=completed_workflow.name,
                status="SUCCESS",
                summary=final_decision.reply_to_user,
                slots_collected={},
            )
            logger.info(f"Child workflow '{completed_workflow.name}' completed, result delivered to parent")

    def _push_child_workflow(
        self,
        session: SessionState,
        target_workflow_id: str,
    ) -> None:
        """
        Push a new frame for the child workflow onto the stack.
        """
        target_workflow = self._workflow_repository.get_workflow(target_workflow_id)
        child_frame = Frame(
            workflow_name=target_workflow_id,
            current_step_id=target_workflow.start_step,
        )
        session.stack.append(child_frame)
        logger.info(f"Pushed child workflow: {target_workflow_id}")

    # ==========================================================================
    # Response Generation
    # ==========================================================================

    async def _generate_transition_decision(
        self,
        session: SessionState,
        previous_step: Step,
        transition: StateMachineTransition,
        decision: StepDecision,
        user_input: str,
    ) -> StepDecision:
        """
        Generate a StepDecision that introduces the new step after a transition.

        Uses context from the previous step to generate a smooth transition message.
        """
        new_frame, _, next_step = self._get_execution_context(session)

        meta = TransitionMeta(
            transition_type=transition,
            reasoning=decision.reasoning,
            workflow_link=self._find_workflow_link(previous_step, decision.result_value),
            child_result=new_frame.pending_child_result,
        )

        return await introduce_step(
            llm=self._llm_provider,
            from_step=previous_step,
            to_step=next_step,
            meta=meta,
            history=session.history,
            user_input=user_input,
        )

    # ==========================================================================
    # Standard Helpers
    # ==========================================================================

    def _get_execution_context(
        self, session: SessionState
    ) -> Tuple[Frame, Workflow, Step]:
        active_frame = session.active_frame
        if not active_frame:
            raise ValueError("Session stack is empty.")
        workflow_def = self._workflow_repository.get_workflow(active_frame.workflow_name)
        step_def = workflow_def.steps[active_frame.current_step_id]
        return active_frame, workflow_def, step_def

    def _workflow_exists(self, workflow_id: str) -> bool:
        return self._workflow_repository.workflow_exists(workflow_id)

    async def _execute_step(
        self,
        active_frame: Frame,
        step_def: Step,
        user_input: Optional[str],
        history: list[Message],
    ) -> StepDecision:
        executor = StepExecutor(self._llm_provider)
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
