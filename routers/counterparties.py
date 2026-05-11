from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from models import Counterparty, User
from schemas import CounterpartyCreate, CounterpartyUpdate, CounterpartyOut, MessageResponse
from routers.auth import get_current_user, require_role
from typing import List, Optional

router = APIRouter()

@router.get("/", response_model=List[CounterpartyOut])
def list_counterparties(
    type: Optional[str] = None,
    search: Optional[str] = None,
    has_debt: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    q = db.query(Counterparty).filter(Counterparty.is_active == True)
    if type:
        q = q.filter(Counterparty.type == type)
    if search:
        q = q.filter(Counterparty.name.ilike(f"%{search}%"))
    if has_debt:
        q = q.filter(Counterparty.balance < 0)
    return q.order_by(Counterparty.name).all()

@router.get("/balances")
def balances_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = db.execute(text("SELECT * FROM v_counterparty_balances ORDER BY ABS(balance) DESC"))
    return [dict(r._mapping) for r in result]

@router.get("/{cp_id}", response_model=CounterpartyOut)
def get_counterparty(
    cp_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cp = db.query(Counterparty).filter(Counterparty.id == cp_id).first()
    if not cp:
        raise HTTPException(404, "Контрагент не найден")
    return cp

@router.post("/", response_model=MessageResponse, status_code=201)
def create_counterparty(
    data: CounterpartyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "accountant"))
):
    cp = Counterparty(**data.model_dump())
    db.add(cp)
    db.flush()
    return {"message": "Контрагент создан", "id": cp.id}

@router.put("/{cp_id}", response_model=MessageResponse)
def update_counterparty(
    cp_id: int,
    data: CounterpartyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "accountant"))
):
    cp = db.query(Counterparty).filter(Counterparty.id == cp_id).first()
    if not cp:
        raise HTTPException(404, "Контрагент не найден")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(cp, k, v)
    return {"message": "Контрагент обновлён", "id": cp_id}

@router.delete("/{cp_id}", response_model=MessageResponse)
def delete_counterparty(
    cp_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    cp = db.query(Counterparty).filter(Counterparty.id == cp_id).first()
    if not cp:
        raise HTTPException(404, "Контрагент не найден")
    cp.is_active = False
    return {"message": "Контрагент деактивирован", "id": cp_id}
