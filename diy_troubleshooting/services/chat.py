"""
Chat Service - Application Orchestration Layer

This service is the entry point for all conversation operations. It orchestrates
the interaction between the Data Layer (Repositories), the Logic Layer (Engine/Router),
and the API. It ensures that sessions are loaded, processed, and saved correctly.
"""

import logging
from typing import Optional

from ..domain.models import Workflow
from ..state.models import Frame, SessionState
from ..repositories.session import SessionRepository
from ..repositories.workflow import WorkflowRepository
from ..execution.engine import WorkflowEngine
from ..schemas.decisions import StepDecision
from .workflow_router import WorkflowRouter

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(
        self,
        session_repository: SessionRepository,
        workflow_repository: WorkflowRepository,
        engine: WorkflowEngine,
        router: WorkflowRouter
    ):
        self.session_repo = session_repository
        self.workflow_repo = workflow_repository
        self.engine = engine
        self.router = router

    def create_session(self) -> SessionState:
        """Creates a new empty session."""
        return self.session_repo.create()

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Retrieves a session (for resuming)."""
        return self.session_repo.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Deletes a session."""
        # Note: SessionRepo needs to implement delete()
        if hasattr(self.session_repo, 'delete'):
             return self.session_repo.delete(session_id)
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
        
        # 1. Load Session
        session = self.session_repo.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # 2. Logic: Cold Start vs. Warm Start
        if not session.stack:
            await self._handle_cold_start(session, user_text)

        # 3. Execute Engine Turn
        # If stack is STILL empty after cold start handling (Router found nothing),
        # we return a fallback response without invoking the engine.
        if not session.stack:
            return {
                "reply": "I'm sorry, I couldn't find a specific troubleshooting guide for that issue. Could you try describing it differently?",
                "status": "FAILED",
                "active_workflow": None
            }

        # Run the Engine
        decision = await self.engine.handle_message(session, user_text)

        # 4. Save Session
        self.session_repo.save(session)

        # 5. Construct Metadata (Title, Progress)
        active_workflow_meta = self._get_active_workflow_metadata(session)

        return {
            "reply": decision.reply_to_user,
            "status": decision.status,
            "active_workflow": active_workflow_meta,
            "debug_info": None # todo: populate this field
        }

    async def _handle_cold_start(self, session: SessionState, user_text: str):
        """
        Uses the Router to find a workflow based on the user's initial query.
        If found, pushes the first Frame onto the stack.
        """
        logger.info(f"Cold Start detected for session {session.session_id}")
        
        match = await self.router.find_best_workflow(user_text)
        
        if match:
            workflow_id, score = match
            logger.info(f"Router selected '{workflow_id}' with score {score}")
            
            # Retrieve the full definition to get the start_step
            # Note: This might trigger a DB fetch in the future (Lazy Loading)
            workflow = self.workflow_repo.get_workflow(workflow_id)
            
            # Push initial frame
            initial_frame = Frame(
                workflow_name=workflow.name,
                current_step_id=workflow.start_step
            )
            session.stack.append(initial_frame)
        else:
            logger.warning("Router found no matching workflow.")

    def _get_active_workflow_metadata(self, session: SessionState) -> Optional[dict]:
        """
        Helper to extract metadata about the current workflow.
        """
        frame = session.active_frame
        if not frame:
            return None
            
        try:
            wf = self.workflow_repo.get_workflow(frame.workflow_name)
            
            # Calculate simple progress (optional improvement: pre-calculate total steps)
            step_count = len(wf.steps)
            
            return {
                "id": wf.name,
                # In the future, 'Workflow' model needs a 'title' field. 
                # For now, we use the name or ID.
                "title": wf.name.replace("_", " ").title(),
                "step_id": frame.current_step_id,
                "total_steps": step_count
            }
        except Exception:
            # Fallback if workflow definition is missing or corrupt
            return None