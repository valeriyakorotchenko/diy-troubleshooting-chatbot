"""
Router Service Interface.

Defines the contract for the "Workflow Router" - the component responsible
for analyzing a user's initial query and selecting the best matching
troubleshooting workflow.
"""
from abc import ABC, abstractmethod
from typing import Optional, Tuple

class WorkflowRouter(ABC):
    @abstractmethod
    async def find_best_workflow(self, user_query: str) -> Optional[Tuple[str, float]]:
        """
        Analyzes the user's input and returns the ID of the best matching workflow
        along with a confidence score (0.0 to 1.0).
        
        Returns:
            (workflow_id, score) or None if no match found.
        """
        pass


class MockWorkflowRouter(WorkflowRouter):
    """
    Temporary Stub: Always returns the 'Lukewarm Water' workflow
    regardless of what the user types.
    """
    async def find_best_workflow(self, user_query: str) -> Optional[Tuple[str, float]]:
        return "troubleshoot_lukewarm_water", 1.0