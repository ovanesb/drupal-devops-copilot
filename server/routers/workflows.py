from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from server.db import get_db
from server import schemas, crud

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("/{id}", response_model=schemas.WorkflowOut)
def get_workflow(id: int, db: Session = Depends(get_db)):
    wf = crud.get_workflow(db, id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@router.post("/{id}", response_model=schemas.WorkflowOut)
def post_workflow(id: int, payload: schemas.WorkflowBase, db: Session = Depends(get_db)):
    # Upsert semantics: create or update the same ID
    wf = crud.upsert_workflow(db, id, payload)
    return wf


@router.put("/{id}", response_model=schemas.WorkflowOut)
def put_workflow(id: int, payload: schemas.WorkflowBase, db: Session = Depends(get_db)):
    wf = crud.update_workflow(db, id, payload)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf
