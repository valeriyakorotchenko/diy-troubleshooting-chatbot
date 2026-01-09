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

from ..domain.models import Step, StepType, Workflow
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

        session.update_history(user_input, final_decision.reply_to_user)
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
                result = WorkflowResult(
                    source_workflow_id=workflow.name,
                    status="SUCCESS",
                    summary=decision.reply_to_user,
                    slots_collected={},
                )
                session.return_from_workflow(result)
                return StateMachineTransition.POP

            # Otherwise, resolve and advance to the next step.
            next_step_id = current_step.resolve_next_step_id(decision.result_value)
            session.advance_to_step(next_step_id)
            return StateMachineTransition.ADVANCE

        # Validate and push the child workflow onto the stack.
        if decision.status == StepStatus.CALL_WORKFLOW:
            target_workflow_id = decision.result_value
            target_workflow = self._workflow_repository.get_workflow(target_workflow_id)
            
            session.enter_workflow(target_workflow_id, target_workflow.start_step)

            return StateMachineTransition.PUSH

        # Unknown status received. Log a warning and hold.
        return StateMachineTransition.HOLD

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
            workflow_link=(
                previous_step.find_workflow_link(decision.result_value)
                if decision.result_value else None
            ),
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
