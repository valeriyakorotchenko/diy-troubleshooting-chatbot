import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Optional

from sqlmodel import Session, select

from ..infrastructure.database.connection import engine
from ..infrastructure.database.tables import SessionDBModel
from ..state.models import SessionState


class SessionRepository(ABC):
    """
    Defines how the application accesses sessions.
    This allows us change how data is accessed (Memory -> SQL -> API) later
    without changing the WorkflowEngine code.
    """

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

    @abstractmethod
    def delete(self, session_id: str) -> bool:
        """Deletes a session. Returns True if found and deleted."""
        pass


class InMemorySessionRepository(SessionRepository):
    """
    Uses in-memory dictionary for session storage for testing/dev purposes.
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

    def delete(self, session_id: str) -> bool:
        if session_id in self._store:
            del self._store[session_id]
            return True
        return False


class PostgresSessionRepository(SessionRepository):
    """
    PostgreSQL + JSONB storage for session state.
    """

    def create(self) -> SessionState:
        # Create the domain session object with a new UUID.
        new_id = str(uuid.uuid4())
        domain_session = SessionState(session_id=new_id)

        # Persist the session to the database.
        db_model = SessionDBModel(
            session_id=new_id, state=domain_session.model_dump(mode="json")
        )

        with Session(engine) as db:
            db.add(db_model)
            db.commit()

        return domain_session

    def get(self, session_id: str) -> Optional[SessionState]:
        with Session(engine) as db:
            statement = select(SessionDBModel).where(
                SessionDBModel.session_id == session_id
            )
            result = db.exec(statement).first()

            if not result:
                return None

            # Deserialize the JSONB data back into a Pydantic domain model.
            session = SessionState(**result.state)
            
            # Inject the timestamp from the SQL column to preserve the actual update time.
            session.updated_at = result.updated_at

            return session

    def save(self, session: SessionState):
        with Session(engine) as db:
            statement = select(SessionDBModel).where(
                SessionDBModel.session_id == session.session_id
            )
            result = db.exec(statement).first()

            if result:
                # Update the JSON blob and the timestamp.
                result.state = session.model_dump(mode="json")
                result.updated_at = datetime.utcnow()
                db.add(result)
                db.commit()
            else:
                # Raise an error if save() is called on a non-existent session.
                raise ValueError(f"Session {session.session_id} does not exist in DB.")

    def delete(self, session_id: str) -> bool:
        with Session(engine) as db:
            statement = select(SessionDBModel).where(
                SessionDBModel.session_id == session_id
            )
            result = db.exec(statement).first()

            if result:
                db.delete(result)
                db.commit()
                return True
            return False
