from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import Response

from ..services.chat import ChatService
from .dependencies import get_chat_service
from .schemas import (
    ChatMessage,
    ChatResponse,
    CreateSessionResponse,
    SessionRead,
    UserMessage,
)

app = FastAPI(title="DIY Agentic Chatbot")

# Endpoint definitions.

@app.post(
    "/sessions",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_session(
    service: ChatService = Depends(get_chat_service)
):
    """Starts a new empty session."""
    session = await service.create_session()
    return CreateSessionResponse(session_id=session.session_id)


@app.get("/sessions/{session_id}", response_model=SessionRead)
async def get_session(
    session_id: str,
    service: ChatService = Depends(get_chat_service)
):
    """
    Retrieves the full session resource.
    Replaces the previous 'Resume' logic with proper resource retrieval.
    """
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    active_frame = session.active_frame
    
    # Transform domain Message objects into API ChatMessage DTOs (Data Transfer Objects).
    # This decouples the internal state model from the public API contract.
    history_dto = [
        ChatMessage(role=msg.role, content=msg.content) 
        for msg in session.history
    ]
    
    return SessionRead(
        session_id=session.session_id,
        status="IN_PROGRESS" if session.stack else "COMPLETED",
        history=history_dto,
        current_workflow=active_frame.workflow_name if active_frame else None,
        updated_at=session.updated_at,
        debug=session.model_dump(mode='json')
    )


@app.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    service: ChatService = Depends(get_chat_service)
):
    """
    Deletes a session. Returns 204 No Content on success.
    """
    success = await service.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Return a Response object with no content for HTTP 204.
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/sessions/{session_id}/messages", response_model=ChatResponse)
async def handle_message(
    session_id: str,
    message: UserMessage,
    service: ChatService = Depends(get_chat_service)
):
    try:
        # Process the message through the chat service.
        turn_result = await service.process_message(session_id, message.text)

        # Map the service TurnResult to the API ChatResponse.
        return ChatResponse(
            reply=turn_result.reply,
            status=turn_result.status,
            debug=None 
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))