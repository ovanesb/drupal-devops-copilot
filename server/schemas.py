from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


# ---------- Workflows ----------
class WorkflowBase(BaseModel):
    name: str
    nodes: Any
    edges: Any


class WorkflowOut(WorkflowBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # pydantic v2 ORM mode


# ---------- Profiles ----------
class ProfileBase(BaseModel):
    name: str
    kind: str
    base_url: Optional[str] = None
    username: Optional[str] = None


class ProfileOut(ProfileBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
