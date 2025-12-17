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
2. If the Agent waits (Transition=HOLD) or finishes (Transition=EXIT),
    the engine yields control back to the client (User Turn).
"""

import logging
from typing import Tuple, Optional
from enum import Enum, auto

from ..state.models import SessionState, Frame, Message
from ..domain.models import Workflow, Step
from ..schemas.decisions import StepStatus, StepDecision
from ..repositories.workflow import WorkflowRepository
from ..llm.interface import LLMProvider
from .executor import StepExecutor

logger = logging.getLogger(__name__)


class DialogueControlAction(Enum):
    """Next dialogie management action"""

    WAIT_FOR_USER_INPUT = auto()  # Yield to user
    CONTINUE_IMMEDIATELY = auto()  # Loop internally


class StateMachineTransition(Enum):
    """
    Strict State Machine terminology describing what happened to the graph pointers.
    This decouples the Engine logic from the LLM's 'StepStatus' - an LLM's assessment
    of goal completion for the current step.
    """

    HOLD = auto()  # Pointer remains on current node
    ADVANCE = auto()  # Pointer moved to the next linear or branched node
    EXIT = auto()  # Stack popped (Workflow completed)


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
        accumulated_reply = []
        current_input = user_input

        final_decision = None
        max_turns = 3
        turn_count = 0

        while turn_count < max_turns:
            turn_count += 1
            if not session.active_frame:
                break

            # 1. Load Context
            active_frame, workflow_def, step_def = self._get_execution_context(session)

            # 2. Execute Step (Worker)
            decision = await self._execute_step(
                active_frame=active_frame,
                step_def=step_def,
                user_input=current_input,
                history=session.history,
            )
            final_decision = decision

            # 3. Apply Decision & TRANSLATE to State Machine Language
            # This is the Anti-Corruption Layer.
            fsm_transition = self._apply_decision(
                session, active_frame, workflow_def, decision
            )

            # 4. Update History
            self._update_history(session, current_input, decision)
            accumulated_reply.append(decision.reply_to_user)

            # 5. Determine Next Action (Pure Finite-State Machine Logic)
            # We look ONLY at the 'transition', ignoring the raw LLM decision.
            dialogue_action = self._derive_control_action(fsm_transition)

            if dialogue_action == DialogueControlAction.CONTINUE_IMMEDIATELY:
                current_input = None
                continue
            else:
                break

        return StepDecision(
            reply_to_user=" ".join(accumulated_reply),
            status=final_decision.status if final_decision else StepStatus.IN_PROGRESS,
            reasoning=final_decision.reasoning if final_decision else "Workflow ended.",
        )

    # ==========================================================================
    # Logic & Control (Pure Domain)
    # ==========================================================================

    def _derive_control_action(
        self, transition: StateMachineTransition
    ) -> DialogueControlAction:
        """
        Derives the loop control signal based purely on FSM (Finite-State Machine) mechanics.
        """
        # Momentum Logic:
        # If the machine ADVANCED, we keep the floor to explain the new node.
        if transition == StateMachineTransition.ADVANCE:
            return DialogueControlAction.CONTINUE_IMMEDIATELY

        # If we HOLD (waiting for user) or EXIT (workflow done), we yield.
        # (Note: In future recursive designs, EXIT might imply CONTINUE to resume parent).
        return DialogueControlAction.WAIT_FOR_USER_INPUT

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
        Mutates the session state AND translates the result into a StateMachineTransition.
        """
        # Case 1: Hold State
        if decision.status == StepStatus.IN_PROGRESS:
            return StateMachineTransition.HOLD

        if decision.status == StepStatus.GIVE_UP:
            return StateMachineTransition.HOLD

        # Case 2: Attempt Advance
        if decision.status == StepStatus.COMPLETE:
            return self._handle_complete_status(session, frame, workflow, decision)

        return StateMachineTransition.HOLD

    def _handle_complete_status(
        self,
        session: SessionState,
        frame: Frame,
        workflow: Workflow,
        decision: StepDecision,
    ) -> StateMachineTransition:
        """
        Calculates the next node and returns ADVANCE or EXIT.
        """
        frame.pending_child_result = None

        # 1. Resolve Next Step ID
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

        # 2. Mutate State & Return Transition Type
        if not next_step_id:
            session.stack.pop()
            return StateMachineTransition.EXIT
        else:
            next_step_def = workflow.steps.get(next_step_id)
            if next_step_def and next_step_def.type == "end":
                session.stack.pop()
                return StateMachineTransition.EXIT
            else:
                frame.current_step_id = next_step_id
                return StateMachineTransition.ADVANCE

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
