from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Unit, User
from schemas import UnitCreate, UnitUpdate, UnitOut, MessageResponse
from routers.auth import get_current_user, require_role
from typing import List

router = APIRouter()


@router.get("/", response_model=List[UnitOut])
def list_units(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    q = db.query(Unit)
    if active_only:
        q = q.filter(Unit.is_active == True)
    return q.order_by(Unit.name).all()


@router.get("/{unit_id}", response_model=UnitOut)
def get_unit(
    unit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    u = db.query(Unit).filter(Unit.id == unit_id).first()
    if not u:
        raise HTTPException(404, "Единица измерения не найдена")
    return u


@router.post("/", response_model=MessageResponse, status_code=201)
def create_unit(
    data: UnitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    existing = db.query(Unit).filter(Unit.short_name == data.short_name).first()
    if existing:
        raise HTTPException(400, "Единица с таким сокращением уже существует")
    unit = Unit(**data.model_dump())
    db.add(unit)
    db.flush()
    return {"message": "Единица измерения создана", "id": unit.id}


@router.put("/{unit_id}", response_model=MessageResponse)
def update_unit(
    unit_id: int,
    data: UnitUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    u = db.query(Unit).filter(Unit.id == unit_id).first()
    if not u:
        raise HTTPException(404, "Единица измерения не найдена")
    existing = db.query(Unit).filter(Unit.short_name == data.short_name, Unit.id != unit_id).first()
    if existing:
        raise HTTPException(400, "Единица с таким сокращением уже существует")
    for k, v in data.model_dump().items():
        setattr(u, k, v)
    return {"message": "Единица измерения обновлена", "id": unit_id}


@router.delete("/{unit_id}", response_model=MessageResponse)
def deactivate_unit(
    unit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    u = db.query(Unit).filter(Unit.id == unit_id).first()
    if not u:
        raise HTTPException(404, "Единица измерения не найдена")
    u.is_active = False
    return {"message": "Единица измерения деактивирована", "id": unit_id}
