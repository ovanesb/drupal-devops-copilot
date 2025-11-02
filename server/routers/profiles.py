from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from server.db import get_db
from server import schemas, crud

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("", response_model=list[schemas.ProfileOut])
def get_profiles(db: Session = Depends(get_db)):
    return crud.list_profiles(db)


@router.post("", response_model=schemas.ProfileOut)
def post_profile(payload: schemas.ProfileBase, db: Session = Depends(get_db)):
    return crud.create_profile(db, payload)


@router.put("", response_model=schemas.ProfileOut)
def put_profile(
    id: int = Query(...),
    payload: Optional[schemas.ProfileBase] = None,
    db: Session = Depends(get_db),
):
    if payload is None:
        raise HTTPException(status_code=400, detail="Missing payload")
    prof = crud.update_profile(db, id=id, data=payload)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    return prof


@router.delete("")
def delete_profile(id: int = Query(...), db: Session = Depends(get_db)):
    ok = crud.delete_profile(db, id)
    if not ok:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"ok": True}
