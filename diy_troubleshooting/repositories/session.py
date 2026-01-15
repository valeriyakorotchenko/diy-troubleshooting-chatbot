import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from sqlmodel import select

from ..infrastructure.database.connection import async_session_factory
from ..infrastructure.database.tables import SessionDBModel
from ..state.models import SessionState


class SessionRepository(ABC):
    """
    Defines how the application accesses sessions.

    All methods are async to keep the event loop unblocked. How this is
    achieved (native async driver vs thread-offloaded sync) is an implementation
    detail encapsulated in concrete subclasses. Callers simply await without
    knowing the underlying mechanism.
    """

    @abstractmethod
    async def create(self) -> SessionState:
        """Creates a new empty session with a unique ID."""
        pass

    @abstractmethod
    async def get(self, session_id: str) -> Optional[SessionState]:
        """Retrieves a session by ID."""
        pass

    @abstractmethod
    async def save(self, session: SessionState) -> None:
        """Persists the session state."""
        pass

    @abstractmethod
    async def delete(self, session_id: str) -> bool:
        """Deletes a session. Returns True if found and deleted."""
        pass


class PostgresSessionRepository(SessionRepository):
    """
    PostgreSQL + JSONB storage for session state.

    Uses asyncpg driver with SQLAlchemy's async extension for native async
    database access without blocking the event loop.
    """

    async def create(self) -> SessionState:
        new_id = str(uuid.uuid4())
        domain_session = SessionState(session_id=new_id)

        db_model = SessionDBModel(
            session_id=new_id, state=domain_session.model_dump(mode="json")
        )

        async with async_session_factory() as session:
            session.add(db_model)
            await session.commit()

        return domain_session

    async def get(self, session_id: str) -> Optional[SessionState]:
        async with async_session_factory() as session:
            statement = select(SessionDBModel).where(
                SessionDBModel.session_id == session_id
            )
            result = await session.execute(statement)
            row = result.scalars().first()

            if not row:
                return None

            domain_session = SessionState(**row.state)
            domain_session.updated_at = row.updated_at

            return domain_session

    async def save(self, session_state: SessionState) -> None:
        async with async_session_factory() as session:
            statement = select(SessionDBModel).where(
                SessionDBModel.session_id == session_state.session_id
            )
            result = await session.execute(statement)
            row = result.scalars().first()

            if row:
                row.state = session_state.model_dump(mode="json")
                row.updated_at = datetime.utcnow()
                session.add(row)
                await session.commit()
            else:
                raise ValueError(
                    f"Session {session_state.session_id} does not exist in DB."
                )

    async def delete(self, session_id: str) -> bool:
        async with async_session_factory() as session:
            statement = select(SessionDBModel).where(
                SessionDBModel.session_id == session_id
            )
            result = await session.execute(statement)
            row = result.scalars().first()

            if row:
                await session.delete(row)
                await session.commit()
                return True
            return False
