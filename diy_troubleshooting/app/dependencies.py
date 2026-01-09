"""
Dependency Injection Wiring (Composition Root).

This module acts as the central "container" for the application's services.
It is responsible for:
1. Instantiating the core Singleton services (Repositories, Adapters, Engine).
2. Wiring them together (e.g., injecting the Repository and LLM Adapter into the Engine).
3. Managing the lifecycle of these objects using @lru_cache to ensure 
   they are created only once per application process.

By consolidating construction logic here, we keep the API layer (main.py) 
clean and strictly focused on routing, while allowing for easy dependency 
overrides during testing.
"""


from functools import lru_cache

from fastapi import Depends

from ..config import settings
from ..execution.engine import WorkflowEngine
from ..llm.adapters.openai_adapter import OpenAIAdapter
from ..llm.interface import LLMProvider
from ..repositories.session import PostgresSessionRepository, SessionRepository
from ..repositories.workflow import PostgresWorkflowRepository, WorkflowRepository
from ..services.chat import ChatService
from ..services.workflow_router import MockWorkflowRouter, WorkflowRouter


# Provides a singleton LLM provider instance.
@lru_cache()
def get_llm_provider() -> LLMProvider:
    return OpenAIAdapter(
        api_key=settings.OPENAI_API_KEY, 
        model_name=settings.OPENAI_MODEL
    )

# Provides a singleton workflow router instance.
@lru_cache()
def get_workflow_router() -> WorkflowRouter:
    return MockWorkflowRouter()

# Provides a singleton workflow repository instance.
@lru_cache()
def get_workflow_repository() -> WorkflowRepository:
    # return StaticWorkflowRepository()
    return PostgresWorkflowRepository()

# Provides a singleton session repository to ensure data persists across requests.
@lru_cache()
def get_session_repository() -> SessionRepository:
    # return InMemorySessionRepository()
    return PostgresSessionRepository()

# Provides a singleton workflow engine to maintain consistent state handling.
@lru_cache()
def get_workflow_engine(
    llm: LLMProvider = Depends(get_llm_provider),
    workflow_repo: WorkflowRepository = Depends(get_workflow_repository)
) -> WorkflowEngine:
    return WorkflowEngine(workflow_repository=workflow_repo, llm_provider=llm)
 
# Provides a singleton chat service to coordinate session and workflow operations.
@lru_cache()
def get_chat_service(
    session_repo: SessionRepository = Depends(get_session_repository),
    workflow_repo: WorkflowRepository = Depends(get_workflow_repository),
    engine: WorkflowEngine = Depends(get_workflow_engine),
    router: WorkflowRouter = Depends(get_workflow_router)
) -> ChatService:
    """
    Injects all necessary components into the ChatService.
    """
    return ChatService(
        session_repository=session_repo,
        workflow_repository=workflow_repo,
        engine=engine,
        router=router
    )