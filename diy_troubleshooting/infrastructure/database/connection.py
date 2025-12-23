"""
Database Connection Manager.

This module handles the low-level details of connecting to PostgreSQL.
It exposes the SQLModel engine which will be used by the Repositories.
"""

from sqlmodel import create_engine, SQLModel
from ...config import settings

# echo=False in production to avoid leaking sensitive data in logs
engine = create_engine(settings.DATABASE_URL, echo=False)


def init_db():
    """
    Idempotent initialization.
    Creates tables if they do not exist.
    Useful for local dev or simple deployments.
    """
    SQLModel.metadata.create_all(engine)
