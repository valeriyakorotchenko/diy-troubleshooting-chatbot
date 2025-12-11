from abc import ABC, abstractmethod
from typing import Dict, Optional
import uuid

from ..state.models import SessionState

class SessionRepository(ABC):
    @abstractmethod
    def create(self) -> SessionState:
        """Creates a new empty session with a unique ID."""
        pass

    @abstractmethod
    def get(self, session_id: str) -> Optional[SessionState]:
        """Retrieves a session by ID."""
        pass

    @abstractmethod
    def save(self, session: SessionState):
        """Persists the session state."""
        pass

class InMemorySessionRepository(SessionRepository):
    """
    For now, we'll use an in-memory dictionary, 
    but this design ensures we can swap it for Redis/Postgres later 
    without changing the API code.
    """

    def __init__(self):
        self._store: Dict[str, SessionState] = {}

    def create(self) -> SessionState:
        new_id = str(uuid.uuid4())
        session = SessionState(session_id=new_id)
        self._store[new_id] = session
        return session

    def get(self, session_id: str) -> Optional[SessionState]:
        return self._store.get(session_id)

    def save(self, session: SessionState):
        self._store[session.session_id] = session