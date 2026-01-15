from abc import ABC, abstractmethod

from sqlmodel import select

from ..domain.models import Workflow
from ..infrastructure.database.connection import async_session_factory
from ..infrastructure.database.tables import WorkflowDBModel


class WorkflowRepository(ABC):
    """
    Defines how the application accesses Workflow definitions.

    All methods are async to keep the event loop unblocked. How this is
    achieved (native async driver vs thread-offloaded sync) is an implementation
    detail encapsulated in concrete subclasses. Callers simply await without
    knowing the underlying mechanism.
    """

    @abstractmethod
    async def get_workflow(self, workflow_id: str) -> Workflow:
        """
        Retrieves a workflow by ID.
        Raises ValueError if not found.
        """
        pass

    async def workflow_exists(self, workflow_id: str) -> bool:
        """
        Check if a workflow exists without raising an exception.
        Default implementation uses get_workflow; subclasses may override for efficiency.
        """
        try:
            await self.get_workflow(workflow_id)
            return True
        except ValueError:
            return False


class PostgresWorkflowRepository(WorkflowRepository):
    """
    Reads from PostgreSQL 'workflows' table (JSONB).

    Uses asyncpg driver with SQLAlchemy's async extension for native async
    database access without blocking the event loop.
    """

    async def get_workflow(self, workflow_id: str) -> Workflow:
        async with async_session_factory() as session:
            statement = select(WorkflowDBModel).where(
                WorkflowDBModel.workflow_id == workflow_id
            )
            result = await session.execute(statement)
            row = result.scalars().first()

            if not row:
                raise ValueError(f"Workflow '{workflow_id}' not found in database.")

            return Workflow(**row.workflow_data)

    async def workflow_exists(self, workflow_id: str) -> bool:
        async with async_session_factory() as session:
            statement = select(WorkflowDBModel.workflow_id).where(
                WorkflowDBModel.workflow_id == workflow_id
            )
            result = await session.execute(statement)
            return result.scalars().first() is not None
