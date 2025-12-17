from abc import ABC, abstractmethod
from typing import Dict

from ..domain.models import Workflow
from ..data.hardcoded_workflows import HARDCODED_WORKFLOWS

# 1. The Interface (Contract)
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

# 2. The Concrete Implementation (Adapter)
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