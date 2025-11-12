from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------- Nodes / Edges ----------
class WorkflowNode(BaseModel):
    id: str
    type: str
    position: Dict[str, Any] = Field(default_factory=dict)
    data: Dict[str, Any] = Field(default_factory=dict)


class WorkflowEdge(BaseModel):
    id: Optional[str] = None
    source: str
    target: str


# ---------- Workflows ----------
class WorkflowBase(BaseModel):
    name: str = "demo"
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)


class WorkflowOut(BaseModel):
    id: int
    name: str
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # Pydantic v2 ORM mode


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
