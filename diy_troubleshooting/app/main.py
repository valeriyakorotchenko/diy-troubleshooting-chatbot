from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Depends

from ..state.models import Frame
from ..execution.engine import WorkflowEngine
from ..repositories.session import SessionRepository
from .dependencies import get_workflow_engine, get_session_repository
from .schemas import CreateSessionResponse, UserMessage, ChatResponse, DebugInfo

app = FastAPI(title="DIY Agentic Chatbot")


# --- Endpoints ---

@app.post("/sessions", response_model=CreateSessionResponse)
def create_session(
    repo: SessionRepository = Depends(get_session_repository)
):
    """Starts a new empty session."""
    session = repo.create()
    return CreateSessionResponse(session_id=session.session_id)

@app.post("/sessions/{session_id}/messages", response_model=ChatResponse)
async def handle_message(
    session_id: str,
    message: UserMessage,
    engine: WorkflowEngine = Depends(get_workflow_engine),
    repo: SessionRepository = Depends(get_session_repository)
):
    """
    The main chat loop.
    1. Loads Session
    2. Checks for Cold Start (if stack is empty)
    3. Runs Engine
    4. Saves Session
    """
    
    # 1. Load Session
    session = repo.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 2. Router / Cold Start Logic
    # Since we haven't implemented the Intent Classifier yet, we will 
    # FORCE the hardcoded workflow for the very first message.
    if not session.stack:
        # HARDCODED at this point: "troubleshoot_lukewarm_water"
        # In the future, 'IntentMatcher.predict(message.text)' goes here.
        start_workflow_id = "troubleshoot_lukewarm_water"
        
        # We need to manually load the definition to get the start step
        # Note: We can access the repo via the engine for convenience, 
        # or inject it separately. Let's use the engine's repo.
        wf_def = engine.repository.get_workflow(start_workflow_id)
        
        initial_frame = Frame(
            workflow_name=start_workflow_id,
            current_step_id=wf_def.start_step
        )
        session.stack.append(initial_frame)

    # 3. Run Engine
    # try:
    decision = await engine.handle_message(session, message.text)
    # except Exception as e:
    #     # Simple error handling for debugging
    #     raise HTTPException(status_code=500, detail=f"Engine Error: {str(e)}")

    # 4. Save State
    repo.save(session)

    # 5. Build Debug Info
    debug_info = None
    active_frame = session.active_frame
    message_history = [msg.model_dump() for msg in session.history]
    if active_frame:
        # Get current step definition
        wf_def = engine.repository.get_workflow(active_frame.workflow_name)
        current_step = wf_def.steps.get(active_frame.current_step_id)
        debug_info = DebugInfo(
            active_frame=active_frame.model_dump(),
            current_step=asdict(current_step) if current_step else None,
            message_history=message_history
        )
    else:
        # Stack is empty (workflow completed)
        debug_info = DebugInfo(active_frame=None, current_step=None, message_history=message_history)

    return ChatResponse(
        reply=decision.reply_to_user,
        status=decision.status,
        debug=debug_info
    )