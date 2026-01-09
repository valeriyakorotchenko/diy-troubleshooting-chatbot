"""
Database Table Definitions.

This module defines the SQL schema using SQLModel.
We use the 'DBModel' suffix to distinguish these persistence models
from the Pydantic domain models (SessionState, Workflow).
"""

from datetime import datetime
from typing import Any, Dict
from uuid import UUID, uuid4

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class SessionDBModel(SQLModel, table=True):
    """
    Persistence model for User Sessions.
    Maps 1-to-1 with the 'sessions' table in Postgres.
    """

    __tablename__ = "sessions"

    session_id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)

    # Store the entire SessionState (stack, history, slots) as JSONB for flexible schema evolution.
    state: Dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WorkflowDBModel(SQLModel, table=True):
    """
    Persistence model for Workflows.
    Maps 1-to-1 with the 'workflows' table in Postgres.
    """

    __tablename__ = "workflows"

    workflow_id: str = Field(primary_key=True)
    title: str

    # Store the entire nested Workflow definition (Steps, Options, Links) as JSONB.
    workflow_data: Dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))

    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
