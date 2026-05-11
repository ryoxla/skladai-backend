from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from models import Transaction, User
from schemas import TransactionCreate, TransactionOut, MessageResponse
from routers.auth import get_current_user, require_role
from typing import List, Optional
from datetime import date

router = APIRouter()

@router.get("/", response_model=List[TransactionOut])
def list_transactions(
    txn_type: Optional[str] = None,
    account_id: Optional[int] = None,
    counterparty_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "accountant"))
):
    query = """
        SELECT t.*, cp.name as counterparty_name, a.name as account_name
        FROM transactions t
        LEFT JOIN counterparties cp ON cp.id = t.counterparty_id
        LEFT JOIN accounts a ON a.id = t.account_id
        WHERE 1=1
    """
    params = {}
    if txn_type:
        query += " AND t.txn_type = :txn_type"
        params["txn_type"] = txn_type
    if account_id:
        query += " AND t.account_id = :acc"
        params["acc"] = account_id
    if counterparty_id:
        query += " AND t.counterparty_id = :cp"
        params["cp"] = counterparty_id
    if date_from:
        query += " AND t.txn_date >= :df"
        params["df"] = date_from
    if date_to:
        query += " AND t.txn_date <= :dt"
        params["dt"] = date_to
    query += " ORDER BY t.txn_date DESC, t.id DESC"
    result = db.execute(text(query), params)
    return [dict(r._mapping) for r in result]

@router.get("/summary")
def cashflow_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "accountant"))
):
    result = db.execute(text(
        "SELECT * FROM v_cashflow_monthly ORDER BY month DESC LIMIT 12"
    ))
    return [dict(r._mapping) for r in result]

@router.get("/{txn_id}", response_model=TransactionOut)
def get_transaction(
    txn_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "accountant"))
):
    result = db.execute(text("""
        SELECT t.*, cp.name as counterparty_name, a.name as account_name
        FROM transactions t
        LEFT JOIN counterparties cp ON cp.id = t.counterparty_id
        LEFT JOIN accounts a ON a.id = t.account_id
        WHERE t.id = :id
    """), {"id": txn_id})
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Операция не найдена")
    return dict(row)

@router.post("/", response_model=MessageResponse, status_code=201)
def create_transaction(
    data: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "accountant"))
):
    if data.txn_type == "transfer" and not data.account_to_id:
        raise HTTPException(400, "Для перевода укажите account_to_id")
    txn = Transaction(**data.model_dump())
    db.add(txn)
    db.flush()
    return {"message": "Операция создана", "id": txn.id}

@router.delete("/{txn_id}", response_model=MessageResponse)
def delete_transaction(
    txn_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "accountant"))
):
    txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if not txn:
        raise HTTPException(404, "Операция не найдена")
    db.delete(txn)
    return {"message": "Операция удалена"}
