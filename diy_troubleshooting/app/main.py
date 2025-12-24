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