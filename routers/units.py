from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Unit, User
from schemas import UnitCreate, UnitOut, MessageResponse
from routers.auth import get_current_user, require_role
from typing import List

router = APIRouter()

@router.get("/", response_model=List[UnitOut])
def list_units(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Unit).order_by(Unit.name).all()

@router.post("/", response_model=MessageResponse, status_code=201)
def create_unit(
    data: UnitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    unit = Unit(**data.model_dump())
    db.add(unit)
    db.flush()
    return {"message": "Единица измерения создана", "id": unit.id}

@router.delete("/{unit_id}", response_model=MessageResponse)
def delete_unit(
    unit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin"))
):
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(404, "Единица не найдена")
    db.delete(unit)
    return {"message": "Единица удалена"}
