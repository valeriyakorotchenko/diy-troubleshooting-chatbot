"""
Engine - Workflow Orchestration Layer

The WorkflowEngine is the deterministic state machine ("The Manager") that
maintains process flow, manages the call stack, and delegates step
execution to the StepExecutor ("The Worker").
-----------------------------------------------

Unlike traditional "Ping-Pong" chatbots (1 Request -> 1 Reply), this engine
is proactive. It executes a loop that continuously advances the workflow
until it hits a blocking state (e.g., waiting for user input).

The Control Logic is "Momentum-Based":
1. If the Agent completes a step and moves to a new one (Transition=ADVANCE),
    the engine perceives "Momentum" and continues the loop immediately
    (System Turn) to explain the new step.
2. If the Agent waits (Transition=HOLD) or finishes (Transition=POP),
    the engine yields control back to the client (User Turn).
"""

import logging
from typing import Tuple, Optional
from enum import Enum, auto

from ..state.models import SessionState, Frame, Message, WorkflowResult
from ..domain.models import Workflow, Step
from ..schemas.decisions import StepStatus, StepDecision
from ..repositories.workflow import WorkflowRepository
from ..llm.interface import LLMProvider
from .executor import StepExecutor

logger = logging.getLogger(__name__)


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


class WorkflowEngine:
    def __init__(self, repository: WorkflowRepository, llm_provider: LLMProvider):
        self.repository = repository
        self.llm_provider = llm_provider

    async def handle_message(
        self, session: SessionState, user_input: str
    ) -> StepDecision:
        """
        The Orchestrator.
        """
        if not session.active_frame:
            raise ValueError("Cannot handle message: session has no active workflow")

        # The loop may execute multiple turns before returning to the user (e.g.,
        # step completes → advance to next step → explain it). Each turn produces
        # a reply, so we accumulate them here to join into one combined response.
        accumulated_reply = []

        current_input = user_input
        decision = None

        # Proactive loop: keeps executing until a step needs user input.           
        for _ in range(3):  # Safety limit to prevent runaway loops
            
            # Load Context
            active_frame, workflow_def, step_def = self._get_execution_context(session)

            # Execute Step (Worker)
            decision = await self._execute_step(
                active_frame=active_frame,
                step_def=step_def,
                user_input=current_input,
                history=session.history,
            )

            # Clear mailbox after consumption (prompt already built, result was read)
            active_frame.pending_child_result = None

            # Apply decision & TRANSLATE to Finite State Machine language
            # This is the Anti-Corruption Layer.
            fsm_transition = self._apply_decision(
                session, active_frame, workflow_def, decision
            )

            # Update History
            self._update_history(session, current_input, decision)
            accumulated_reply.append(decision.reply_to_user)

            # Determine Next Dialogue Action (Pure Finite-State Machine Logic)
            if self._should_take_system_turn(session, fsm_transition):
                current_input = None  # System turn: no user input
            else:
                break  # User turn: yield control

        return StepDecision(
            reply_to_user=" ".join(accumulated_reply),
            status=decision.status,
            reasoning=decision.reasoning,
        )

    # ==========================================================================
    # Logic & Control (Pure Domain)
    # ==========================================================================

    def _should_take_system_turn(
        self, session: SessionState, transition: StateMachineTransition
    ) -> bool:
        """
        Momentum logic: continue on forward progress, yield on blocking states.
        """
        # Forward momentum: ADVANCE or PUSH means we take another system turn immediately
        if transition in (StateMachineTransition.ADVANCE, StateMachineTransition.PUSH):
            return True

        # Parent waiting: if we popped but there's still a parent frame, resume it immediately
        # (take another system turn)
        if transition == StateMachineTransition.POP and session.stack:
            return True

        # Blocking: step in progress, waiting for user input
        if transition == StateMachineTransition.HOLD:
            return False

        # Terminal: root workflow completed, session finished
        if transition == StateMachineTransition.POP and not session.stack:
            return False

        # Defensive fallback for unknown transitions
        return False

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
        self, session: SessionState, user_input: Optional[str], decision: StepDecision
    ):
        if user_input:
            session.history.append(Message(role="user", content=user_input))
        session.history.append(
            Message(role="assistant", content=decision.reply_to_user)
        )
