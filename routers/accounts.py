from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Account, User
from schemas import AccountCreate, AccountUpdate, AccountOut, MessageResponse
from routers.auth import get_current_user, require_role
from typing import List

router = APIRouter()

@router.get("/", response_model=List[AccountOut])
def list_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "accountant"))
):
    return db.query(Account).where(Account.is_active == True).order_by(Account.name).all()

@router.post("/", response_model=MessageResponse, status_code=201)
def create_account(
    data: AccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "accountant"))
):
    acc = Account(**data.model_dump())
    db.add(acc)
    db.flush()
    return {"message": "Счёт создан", "id": acc.id}

@router.put("/{acc_id}", response_model=MessageResponse)
def update_account(
    acc_id: int,
    data: AccountUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "accountant"))
):
    acc = db.query(Account).filter(Account.id == acc_id).first()
    if not acc:
        raise HTTPException(404, "Счёт не найден")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(acc, k, v)
    return {"message": "Счёт обновлён", "id": acc_id}

@router.delete("/{acc_id}", response_model=MessageResponse)
def delete_account(
    acc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin"))
):
    acc = db.query(Account).filter(Account.id == acc_id).first()
    if not acc:
        raise HTTPException(404, "Счёт не найден")
    acc.is_active = False
    return {"message": "Счёт деактивирован"}
