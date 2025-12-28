"""
Service Layer Exceptions

Custom exceptions for the ChatService and related orchestration logic.
"""


class NoMatchingWorkflowError(Exception):
    """Raised when the router cannot find a workflow for the user's query."""
    pass
