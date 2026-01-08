from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Depends

from .dependencies import get_chat_service
from ..services.chat import ChatService
from ..services.exceptions import NoMatchingWorkflowError
from .schemas import CreateSessionResponse, UserMessage, ChatResponse, DebugInfo


app = FastAPI(title="DIY Agentic Chatbot")


# --- Endpoints ---

@app.post("/sessions", response_model=CreateSessionResponse)
def create_session(
    service: ChatService = Depends(get_chat_service)
):
    """Starts a new empty session."""
    session = service.create_session()
    return CreateSessionResponse(session_id=session.session_id)

@app.get("/sessions/{session_id}", response_model=ChatResponse)
def get_session_state(
    session_id: str,
    service: ChatService = Depends(get_chat_service)
):
    """Resumes an existing session."""
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Construct a "Resume" response (Active Workflow + Last Message)
    active_meta = service._get_active_workflow_metadata(session)
    last_reply = session.history[-1].content if session.history else "Welcome back."
    
    return ChatResponse(
        reply=last_reply,
        status="IN_PROGRESS" if session.stack else "COMPLETED",
        active_workflow=active_meta
    )

@app.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    service: ChatService = Depends(get_chat_service)
):
    """Deletes a session."""
    success = service.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted"}

@app.post("/sessions/{session_id}/messages", response_model=ChatResponse)
async def handle_message(
    session_id: str,
    message: UserMessage,
    service: ChatService = Depends(get_chat_service)
):
    """
    The main chat loop. Delegates entirely to the Service Layer.
    """
    try:
        result = await service.process_message(session_id, message.text)
        return result
    except NoMatchingWorkflowError:
        raise HTTPException(
            status_code=422,
            detail="No troubleshooting guide found for your issue. Try describing it differently."
        )