from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from . import models, schemas


# ---------- helpers ----------
def _db_get(db: Session, model, pk: int):
    """Support both SQLAlchemy 1.4/2.0 styles."""
    if hasattr(db, "get"):  # SA 2.0
        return db.get(model, pk)
    return db.query(model).get(pk)  # type: ignore[attr-defined]


# ---------- Workflows ----------
def get_workflow(db: Session, id: int) -> Optional[models.Workflow]:
    return _db_get(db, models.Workflow, id)


def upsert_workflow(db: Session, id: int, data: schemas.WorkflowBase) -> models.Workflow:
    wf = _db_get(db, models.Workflow, id)
    if wf is None:
        wf = models.Workflow(id=id)
        db.add(wf)
    wf.name = data.name
    wf.nodes = data.nodes
    wf.edges = data.edges
    db.commit()
    db.refresh(wf)
    return wf


def update_workflow(db: Session, id: int, data: schemas.WorkflowBase) -> Optional[models.Workflow]:
    wf = _db_get(db, models.Workflow, id)
    if wf is None:
        return None
    wf.name = data.name
    wf.nodes = data.nodes
    wf.edges = data.edges
    db.commit()
    db.refresh(wf)
    return wf


# ---------- Profiles ----------
def list_profiles(db: Session) -> list[models.Profile]:
    return db.query(models.Profile).order_by(models.Profile.id.asc()).all()


def create_profile(db: Session, data: schemas.ProfileBase) -> models.Profile:
    p = models.Profile(
        name=data.name,
        kind=data.kind,
        base_url=data.base_url,
        username=data.username,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def update_profile(db: Session, id: int, data: schemas.ProfileBase) -> Optional[models.Profile]:
    p = _db_get(db, models.Profile, id)
    if p is None:
        return None
    p.name = data.name
    p.kind = data.kind
    p.base_url = data.base_url
    p.username = data.username
    db.commit()
    db.refresh(p)
    return p


def delete_profile(db: Session, id: int) -> bool:
    p = _db_get(db, models.Profile, id)
    if p is None:
        return False
    db.delete(p)
    db.commit()
    return True
