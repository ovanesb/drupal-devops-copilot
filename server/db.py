# server/db.py
from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Pick up from docker-compose env or default to local postgres
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@db:5432/copilot",
)

# Create engine + session factory
engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    future=True,
)

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency to provide a scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
