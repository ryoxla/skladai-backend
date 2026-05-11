from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Warehouse, User
from schemas import WarehouseCreate, WarehouseOut, MessageResponse
from routers.auth import get_current_user, require_role
from typing import List

router = APIRouter()

@router.get("/", response_model=List[WarehouseOut])
def list_warehouses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Warehouse).filter(Warehouse.is_active == True).order_by(Warehouse.name).all()

@router.post("/", response_model=MessageResponse, status_code=201)
def create_warehouse(
    data: WarehouseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    wh = Warehouse(**data.model_dump())
    db.add(wh)
    db.flush()
    return {"message": "Склад создан", "id": wh.id}

@router.put("/{wh_id}", response_model=MessageResponse)
def update_warehouse(
    wh_id: int,
    data: WarehouseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    wh = db.query(Warehouse).filter(Warehouse.id == wh_id).first()
    if not wh:
        raise HTTPException(404, "Склад не найден")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(wh, k, v)
    return {"message": "Склад обновлён", "id": wh_id}
