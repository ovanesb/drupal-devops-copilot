# server/models.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import JSONB

Base = declarative_base()


class Workflow(Base):
    __tablename__ = "workflows"

    id: int = Column(Integer, primary_key=True, index=True)
    name: str = Column(String(255), nullable=False, default="demo")
    # Store as JSON arrays; default to [] both at ORM-level and DB-level
    nodes: Any = Column(JSONB, nullable=False, default=list, server_default="[]")
    edges: Any = Column(JSONB, nullable=False, default=list, server_default="[]")
    created_at: datetime = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Optional[datetime] = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Workflow id={self.id} name={self.name!r}>"


class Profile(Base):
    __tablename__ = "profiles"

    id: int = Column(Integer, primary_key=True, index=True)
    name: str = Column(String(255), nullable=False)
    kind: str = Column(String(64), nullable=False)  # e.g., "jira", "gitlab", "openai"
    base_url: Optional[str] = Column(String(512), nullable=True)
    username: Optional[str] = Column(String(255), nullable=True)
    created_at: datetime = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Optional[datetime] = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Profile id={self.id} name={self.name!r} kind={self.kind!r}>"
