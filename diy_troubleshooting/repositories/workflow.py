from abc import ABC, abstractmethod
from typing import Dict

from sqlmodel import Session, select

from ..domain.models import Workflow
from ..infrastructure.database.tables import WorkflowDBModel
from ..infrastructure.database.connection import engine
from ..data.hardcoded_workflows import HARDCODED_WORKFLOWS


# The Interface
class WorkflowRepository(ABC):
    """
    Defines how the application accesses Workflow definitions.
    This allows us change how data is accessed (Memory -> SQL -> API) later
    without changing the WorkflowEngine code.
    """

    @abstractmethod
    def get_workflow(self, workflow_id: str) -> Workflow:
        """
        Retrieves a workflow by ID.
        Raises ValueError if not found.
        """
        pass


class StaticWorkflowRepository(WorkflowRepository):
    """
    Get workflows from a hardcoded list in memory.
    """

    def __init__(self):
        # Index for O(1) lookup
        self._index: Dict[str, Workflow] = HARDCODED_WORKFLOWS

    def get_workflow(self, workflow_id: str) -> Workflow:
        if workflow_id not in self._index:
            raise ValueError(f"Workflow '{workflow_id}' not found.")
        return self._index[workflow_id]


class PostgresWorkflowRepository(WorkflowRepository):
    """
    Reads from PostgreSQL 'workflows' table (JSONB).
    """

    def get_workflow(self, workflow_id: str) -> Workflow:
        with Session(engine) as db:
            statement = select(WorkflowDBModel).where(
                WorkflowDBModel.workflow_id == workflow_id
            )
            result = db.exec(statement).first()

            if not result:
                raise ValueError(f"Workflow '{workflow_id}' not found in database.")

            # Deserialize JSONB -> Pydantic
            return Workflow(**result.workflow_data)
