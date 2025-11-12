from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from server.db import get_db
from server import schemas, models

router = APIRouter(prefix="/workflows", tags=["workflows"])

def _to_plain_nodes(nodes):
    out = []
    for n in nodes:
        if hasattr(n, "model_dump"):
            out.append(n.model_dump())
        elif hasattr(n, "dict"):
            out.append(n.dict())
        else:
            out.append(n)
    return out

def _to_plain_edges(edges):
    out = []
    for e in edges:
        if hasattr(e, "model_dump"):
            out.append(e.model_dump())
        elif hasattr(e, "dict"):
            out.append(e.dict())
        else:
            out.append(e)
    return out

@router.get("/{id}", response_model=schemas.WorkflowOut)
def get_workflow(id: int, db: Session = Depends(get_db)):
    # SQLAlchemy 2.x style
    wf = db.get(models.Workflow, id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return schemas.WorkflowOut(
        id=wf.id,
        name=wf.name,
        nodes=wf.nodes or [],
        edges=wf.edges or [],
        created_at=wf.created_at,
        updated_at=wf.updated_at,
    )

@router.post("/{id}", response_model=schemas.WorkflowOut)
def post_workflow(id: int, payload: schemas.WorkflowBase, db: Session = Depends(get_db)):
    wf = db.get(models.Workflow, id)
    if not wf:
        wf = models.Workflow(id=id, name=payload.name or "demo", nodes=[], edges=[])
        db.add(wf)

    wf.name = payload.name or wf.name
    wf.nodes = _to_plain_nodes(payload.nodes)
    wf.edges = _to_plain_edges(payload.edges)

    db.commit()
    db.refresh(wf)
    return schemas.WorkflowOut(
        id=wf.id,
        name=wf.name,
        nodes=wf.nodes or [],
        edges=wf.edges or [],
        created_at=wf.created_at,
        updated_at=wf.updated_at,
    )

@router.put("/{id}", response_model=schemas.WorkflowOut)
def put_workflow(id: int, payload: schemas.WorkflowBase, db: Session = Depends(get_db)):
    wf = db.get(models.Workflow, id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    wf.name = payload.name or wf.name
    wf.nodes = _to_plain_nodes(payload.nodes)
    wf.edges = _to_plain_edges(payload.edges)

    db.commit()
    db.refresh(wf)
    return schemas.WorkflowOut(
        id=wf.id,
        name=wf.name,
        nodes=wf.nodes or [],
        edges=wf.edges or [],
        created_at=wf.created_at,
        updated_at=wf.updated_at,
    )
