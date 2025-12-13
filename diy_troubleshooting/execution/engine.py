"""
Engine - Workflow Orchestration Layer

The WorkflowEngine is the deterministic state machine ("Manager") that
maintains process flow, manages the call stack, and delegates step
execution to the StepExecutor.
"""

import logging
from typing import Optional

from ..state.models import SessionState, Frame, Message, WorkflowResult
from ..domain.models import Workflow
from ..schemas.decisions import StepStatus, StepDecision
from ..repositories.workflow import WorkflowRepository
from ..llm.interface import LLMProvider
from .executor import StepExecutor

logger = logging.getLogger(__name__)

class WorkflowEngine:
    # Depends on the LLMProvider and WorkflowRepository
    def __init__(self, repository: WorkflowRepository, llm_provider: LLMProvider):
        self.repository = repository
        self.llm_provider = llm_provider

    async def handle_message(self, session: SessionState, user_input: str) -> StepDecision:
        """
        The main entry point. Receives user input, runs the current step,
        updates state, and returns the response.
        """

        # 1. Identify where we are
        active_frame = session.active_frame
        if not active_frame:
            raise ValueError("Session stack is empty.")

        # 2. Get Workflow and Step Definitions from Repository
        workflow_def = self.repository.get_workflow(active_frame.workflow_name)
        step_def = workflow_def.steps[active_frame.current_step_id]

        # 3. Execute the Turn (The 'Logic' part)
        # Note: We instantiate Executor per-request, but inject the heavy Provider
        executor = StepExecutor(self.llm_provider)
        
        decision = await executor.run_turn(
            step=step_def,
            frame=active_frame,
            user_input=user_input,
            history=session.history
        )

        # 4. State Transition Logic (The 'State Machine' part)
        await self._apply_decision(session, active_frame, workflow_def, decision)

        # 5. Append interaction to History
        # (the original input and the final reply)
        if user_input:
            session.history.append(Message(role="user", content=user_input))
        session.history.append(Message(role="assistant", content=decision.reply_to_user))

        return decision

    async def _apply_decision(
        self, 
        session: SessionState, 
        frame: Frame, 
        workflow: Workflow, 
        decision: StepDecision
    ):
        """
        Updates the SessionState based on the LLM's decision.
        """

        if decision.status == StepStatus.IN_PROGRESS:
            # Stay on current step. Do nothing to the stack.
            pass

        elif decision.status == StepStatus.COMPLETE:
            # Clear any pending child results (we consumed them)
            frame.pending_child_result = None
            
            # Logic: Determine Next Step
            current_step = workflow.steps[frame.current_step_id]
            next_step_id = None
            
            # Case A: Choice-based branching
            if current_step.type == "ask_choice" and current_step.options:
                # Find the option that matches the result_value
                selected_option = next((opt for opt in current_step.options if opt.id == decision.result_value), None)
                next_step_id = selected_option.next_step_id if selected_option else current_step.next_step
            
            # Case B: Linear flow - for all other step types, use default next_step
            else:
                next_step_id = current_step.next_step

            # WORKFLOW TERMINATION CHECK
            # If next_step is None or type is 'end', we pop the stack (Workflow Complete)
            # For this MVP, let's assume if the step ID starts with "end_", it's over.
            if not next_step_id:
                # End of workflow
                session.stack.pop()
            else:
                # Check if the *next* step is an end node
                next_step_def = workflow.steps.get(next_step_id)
                if next_step_def and next_step_def.type == "end":
                    # We are done. Pop the stack.
                    session.stack.pop()
                else:
                    # Advance the pointer
                    frame.current_step_id = next_step_id

        elif decision.status == StepStatus.GIVE_UP:
            pass