from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from decimal import Decimal
from database import get_db
from models import Transaction, Account, Counterparty, User
from schemas import TransactionCreate, TransactionUpdate, TransactionOut, MessageResponse
from routers.auth import get_current_user, require_role
from typing import List, Optional
from datetime import date

router = APIRouter()


def recalculate_account_balance(db: Session, account_id: int):
    """Пересчёт баланса счёта по всем проведённым транзакциям."""
    result = db.execute(text("""
        SELECT COALESCE(SUM(CASE txn_type
            WHEN 'income'   THEN amount
            WHEN 'expense'  THEN -amount
            WHEN 'transfer' THEN -amount
            ELSE 0
        END), 0) as balance
        FROM transactions
        WHERE account_id = :acc_id AND status = 'confirmed'
    """), {"acc_id": account_id})
    balance = result.scalar() or Decimal("0")

    result2 = db.execute(text("""
        SELECT COALESCE(SUM(amount), 0) as incoming
        FROM transactions
        WHERE account_to_id = :acc_id AND txn_type = 'transfer' AND status = 'confirmed'
    """), {"acc_id": account_id})
    incoming = result2.scalar() or Decimal("0")

    acc = db.query(Account).filter(Account.id == account_id).first()
    if acc:
        acc.balance = balance + incoming


def recalculate_counterparty_balance(db: Session, counterparty_id: int):
    """Пересчёт баланса контрагента по документам и проведённым транзакциям."""
    result = db.execute(text("""
        SELECT COALESCE(SUM(CASE doc_type
            WHEN 'receipt'    THEN total_amount
            WHEN 'return_in'  THEN -total_amount
            WHEN 'shipment'   THEN -total_amount
            WHEN 'return_out' THEN total_amount
            ELSE 0
        END), 0) as doc_balance
        FROM documents
        WHERE counterparty_id = :cp_id AND status = 'confirmed'
    """), {"cp_id": counterparty_id})
    doc_balance = result.scalar() or Decimal("0")

    result2 = db.execute(text("""
        SELECT COALESCE(SUM(CASE txn_type
            WHEN 'income'  THEN  amount
            WHEN 'expense' THEN -amount
            ELSE 0
        END), 0) as txn_balance
        FROM transactions
        WHERE counterparty_id = :cp_id AND status = 'confirmed'
    """), {"cp_id": counterparty_id})
    txn_balance = result2.scalar() or Decimal("0")

    cp = db.query(Counterparty).filter(Counterparty.id == counterparty_id).first()
    if cp:
        cp.balance = doc_balance + txn_balance


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

    txn_data = data.model_dump()
    txn_data["status"] = "draft"
    txn = Transaction(**txn_data)
    db.add(txn)
    db.flush()

    return {"message": "Операция создана (не проведена)", "id": txn.id}


@router.put("/{txn_id}/confirm", response_model=MessageResponse)
def confirm_transaction(
    txn_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "accountant"))
):
    txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if not txn:
        raise HTTPException(404, "Операция не найдена")
    if txn.status == "confirmed":
        raise HTTPException(400, "Операция уже проведена")

    # Проверка достаточности средств для расхода
    if txn.txn_type == "expense":
        acc = db.query(Account).filter(Account.id == txn.account_id).first()
        if acc and acc.balance < txn.amount:
            raise HTTPException(400, f"Недостаточно средств на счёте «{acc.name}»: баланс {acc.balance}, требуется {txn.amount}")

    txn.status = "confirmed"
    db.flush()

    if txn.account_id:
        recalculate_account_balance(db, txn.account_id)
    if txn.account_to_id:
        recalculate_account_balance(db, txn.account_to_id)
    if txn.counterparty_id:
        recalculate_counterparty_balance(db, txn.counterparty_id)

    return {"message": "Операция проведена", "id": txn_id}


@router.put("/{txn_id}/cancel", response_model=MessageResponse)
def cancel_transaction(
    txn_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "accountant"))
):
    txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if not txn:
        raise HTTPException(404, "Операция не найдена")
    if txn.status != "confirmed":
        raise HTTPException(400, "Можно отменить только проведённую операцию")

    txn.status = "draft"
    db.flush()

    if txn.account_id:
        recalculate_account_balance(db, txn.account_id)
    if txn.account_to_id:
        recalculate_account_balance(db, txn.account_to_id)
    if txn.counterparty_id:
        recalculate_counterparty_balance(db, txn.counterparty_id)

    return {"message": "Проведение операции отменено", "id": txn_id}


@router.put("/{txn_id}", response_model=MessageResponse)
def update_transaction(
    txn_id: int,
    data: TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "accountant"))
):
    txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if not txn:
        raise HTTPException(404, "Операция не найдена")

    was_confirmed = txn.status == "confirmed"
    old_account_id = txn.account_id
    old_account_to_id = txn.account_to_id
    old_counterparty_id = txn.counterparty_id

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(txn, field, value)
    db.flush()

    if was_confirmed:
        accounts_to_recalc = {old_account_id, txn.account_id}
        if old_account_to_id:
            accounts_to_recalc.add(old_account_to_id)
        if txn.account_to_id:
            accounts_to_recalc.add(txn.account_to_id)
        for acc_id in accounts_to_recalc:
            if acc_id:
                recalculate_account_balance(db, acc_id)

        counterparties_to_recalc = {old_counterparty_id, txn.counterparty_id}
        for cp_id in counterparties_to_recalc:
            if cp_id:
                recalculate_counterparty_balance(db, cp_id)

    return {"message": "Операция обновлена", "id": txn_id}


@router.delete("/{txn_id}", response_model=MessageResponse)
def delete_transaction(
    txn_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "accountant"))
):
    txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if not txn:
        raise HTTPException(404, "Операция не найдена")
    if txn.status == "confirmed":
        raise HTTPException(400, "Нельзя удалить проведённую операцию. Сначала отмените проведение.")

    db.delete(txn)
    return {"message": "Операция удалена"}
