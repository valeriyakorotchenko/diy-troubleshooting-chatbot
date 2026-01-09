"""
Chat Service - Application Orchestration Layer

This service is the entry point for all conversation operations. It orchestrates
the interaction between the Data Layer (Repositories), the Logic Layer (Engine/Router),
and the API. It ensures that sessions are loaded, processed, and saved correctly.
"""

import logging
from typing import Optional

from pydantic import BaseModel

from ..execution.engine import WorkflowEngine
from ..execution.schemas.decisions import StepDecision
from ..repositories.session import SessionRepository
from ..repositories.workflow import WorkflowRepository
from ..state.models import Frame, SessionState
from .workflow_router import WorkflowRouter

logger = logging.getLogger(__name__)


class ChatTurnResult(BaseModel):
    """
    The outcome of a single conversation turn.
    Contains the final reply, the status of the process, and the 
    raw engine decision for logging/debugging.
    """
    reply: str
    status: str
    decision: Optional[StepDecision] # Optional to handle fallback/error cases
    session_id: str


class ChatService:
    def __init__(
        self,
        session_repository: SessionRepository,
        workflow_repository: WorkflowRepository,
        engine: WorkflowEngine,
        router: WorkflowRouter
    ):
        self._session_repo = session_repository
        self._workflow_repo = workflow_repository
        self._engine = engine
        self._router = router

    def create_session(self) -> SessionState:
        """Creates a new empty session."""
        return self._session_repo.create()

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Retrieves a session (for resuming)."""
        return self._session_repo.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Deletes a session."""
        # Note: SessionRepo needs to implement delete()
        if hasattr(self._session_repo, 'delete'):
             return self._session_repo.delete(session_id)
        return False

    async def process_message(self, session_id: str, user_text: str) -> dict:
        """
        The Core Loop:
        1. Load Session
        2. Handle Cold Start (Router) vs Warm Start
        3. Execute Engine Turn
        4. Save Session
        5. Return Rich Response
        """
        
        # Load the session from the repository.
        session = self._session_repo.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Handle cold start if no workflow is active yet.
        if not session.stack:
            await self._handle_cold_start(session, user_text)

        # If the stack is still empty after cold start handling (router found nothing),
        # return a fallback response without invoking the engine.
        if not session.stack:
            return ChatTurnResult(
                reply="I'm sorry, I couldn't find a specific troubleshooting guide for that issue. Could you try describing it differently?",
                status="FAILED",
                decision=None,
                session_id=session.session_id
            )

        # Run the engine to process the user's message.
        decision = await self._engine.handle_message(session, user_text)

        # Save the updated session state.
        self._session_repo.save(session)

        return ChatTurnResult(
                reply=decision.reply_to_user,
                status=decision.status,
                decision=decision,
                session_id=session.session_id
            )

    async def _handle_cold_start(self, session: SessionState, user_text: str):
        """
        Uses the Router to find a workflow based on the user's initial query.
        If found, pushes the first Frame onto the stack.
        """
        logger.info(f"Cold Start detected for session {session.session_id}")
        
        match = await self._router.find_best_workflow(user_text)
        
        if match:
            workflow_id, score = match
            logger.info(f"Router selected '{workflow_id}' with score {score}")
            
            # Retrieve the full workflow definition to get the start_step.
            workflow = self._workflow_repo.get_workflow(workflow_id)
            
            # Push the initial frame onto the session stack.
            initial_frame = Frame(
                workflow_name=workflow.name,
                current_step_id=workflow.start_step
            )
            session.stack.append(initial_frame)
        else:
            logger.warning("Router found no matching workflow.")
