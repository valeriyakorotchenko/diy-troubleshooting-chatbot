"""
Engine - Workflow Orchestration Layer

The WorkflowEngine is the deterministic state machine ("Manager") that
maintains process flow, manages the call stack, and delegates step
execution to the StepExecutor.
"""

import logging
from typing import Tuple

from ..state.models import SessionState, Frame, Message
from ..domain.models import Workflow, Step
from ..schemas.decisions import StepStatus, StepDecision
from ..repositories.workflow import WorkflowRepository
from ..llm.interface import LLMProvider
from .executor import StepExecutor

logger = logging.getLogger(__name__)

class WorkflowEngine:
    def __init__(self, repository: WorkflowRepository, llm_provider: LLMProvider):
        self.repository = repository
        self.llm_provider = llm_provider

    async def handle_message(self, session: SessionState, user_input: str) -> StepDecision:
        """
        The Orchestrator.
        Currently runs a single 'Ping-Pong' turn (User -> Agent -> State Update).
        (no proactive turns from the agent)
        """
        
        # 1. Load Context (Frame & Definitions)
        active_frame, workflow_def, step_def = self._get_execution_context(session)

        # 2. Execute Step (The Worker)
        decision = await self._execute_step(
            active_frame=active_frame,
            step_def=step_def,
            user_input=user_input,
            history=session.history
        )

        # 3. Apply Decision (The State Machine)
        await self._apply_decision(session, active_frame, workflow_def, decision)

        # 4. Update History (The Logger)
        self._update_history(session, user_input, decision)

        return decision

    # --- Helper Methods ---

    def _get_execution_context(self, session: SessionState) -> Tuple[Frame, Workflow, Step]:
        """
        Retrieves the necessary data to run the current turn.
        """
        active_frame = session.active_frame
        if not active_frame:
            raise ValueError("Session stack is empty. Workflow has ended or not started.")
        
        workflow_def = self.repository.get_workflow(active_frame.workflow_name)
        step_def = workflow_def.steps[active_frame.current_step_id]
        
        return active_frame, workflow_def, step_def

    async def _execute_step(
        self, 
        active_frame: Frame, 
        step_def: Step, 
        user_input: str, 
        history: list[Message]
    ) -> StepDecision:
        """
        Instantiates a fresh Executor and gets the LLM's decision.
        """
        executor = StepExecutor(self.llm_provider)
        return await executor.run_turn(
            step=step_def,
            frame=active_frame,
            user_input=user_input,
            history=history
        )

    async def _apply_decision(
        self, 
        session: SessionState, 
        frame: Frame, 
        workflow: Workflow, 
        decision: StepDecision
    ):
        """
        Updates the SessionState based on the LLM's decision.
        Handles transitions, option selection, and stack management.
        """
        if decision.status == StepStatus.IN_PROGRESS:
            return  # No state change needed

        if decision.status == StepStatus.COMPLETE:
            self._handle_complete_status(session, frame, workflow, decision)
            
        elif decision.status == StepStatus.GIVE_UP:
            pass # In future, this might trigger an escalation flag

    def _handle_complete_status(
        self, 
        session: SessionState, 
        frame: Frame, 
        workflow: Workflow, 
        decision: StepDecision
    ):
        """Logic for advancing the workflow pointer when a step is done."""
        # 1. Clear mailbox
        frame.pending_child_result = None
        
        # 2. Determine Next Step ID
        current_step = workflow.steps[frame.current_step_id]
        next_step_id = None
        
        # Branching vs Linear Logic
        if current_step.type == "ask_choice" and current_step.options:
            selected_option = next(
                (opt for opt in current_step.options if opt.id == decision.result_value), 
                None
            )
            next_step_id = selected_option.next_step_id if selected_option else current_step.next_step
        else:
            next_step_id = current_step.next_step

        # 3. Update Pointers
        if not next_step_id:
            session.stack.pop() # End of Workflow
        else:
            # Check if next step is an explicit 'end' node
            next_step_def = workflow.steps.get(next_step_id)
            if next_step_def and next_step_def.type == "end":
                session.stack.pop()
            else:
                frame.current_step_id = next_step_id

    def _update_history(self, session: SessionState, user_input: str, decision: StepDecision):
        """
        Appends the interaction to the session history.
        """
        if user_input:
            session.history.append(Message(role="user", content=user_input))
        
        session.history.append(Message(role="assistant", content=decision.reply_to_user))