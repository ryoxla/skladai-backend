from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from decimal import Decimal
from database import get_db
from models import Document, DocumentItem, Counterparty, Stock, User
from schemas import DocumentCreate, DocumentUpdate, DocumentOut, MessageResponse
from routers.auth import get_current_user, require_role
from typing import List, Optional
from datetime import date

router = APIRouter()

RECALC_SQL = """
    INSERT INTO stock (product_id, warehouse_id, qty)
    SELECT
        di.product_id,
        d.warehouse_id,
        SUM(di.qty * CASE d.doc_type
            WHEN 'receipt'    THEN 1
            WHEN 'shipment'   THEN -1
            WHEN 'return_in'  THEN 1
            WHEN 'return_out' THEN -1
            WHEN 'writeoff'   THEN -1
            ELSE 0
        END)
    FROM document_items di
    JOIN documents d ON d.id = di.document_id
    WHERE d.status = 'confirmed'
      AND d.warehouse_id IS NOT NULL
    GROUP BY di.product_id, d.warehouse_id
"""

def recalculate_stock(db: Session):
    db.execute(text("DELETE FROM stock"))
    db.execute(text(RECALC_SQL))

def recalculate_counterparty_balance(db: Session, counterparty_id: int):
    """Полный пересчёт баланса контрагента по всем проведённым документам и транзакциям."""
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


@router.get("/", response_model=List[DocumentOut])
def list_documents(
    doc_type: Optional[str] = None,
    status: Optional[str] = None,
    counterparty_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = """
        SELECT d.*, cp.name as counterparty_name, w.name as warehouse_name
        FROM documents d
        LEFT JOIN counterparties cp ON cp.id = d.counterparty_id
        LEFT JOIN warehouses w ON w.id = d.warehouse_id
        WHERE 1=1
    """
    params = {}
    if doc_type:
        query += " AND d.doc_type = :doc_type"
        params["doc_type"] = doc_type
    if status:
        query += " AND d.status = :status"
        params["status"] = status
    if counterparty_id:
        query += " AND d.counterparty_id = :cp"
        params["cp"] = counterparty_id
    query += " ORDER BY d.doc_date DESC, d.id DESC"
    result = db.execute(text(query), params)
    rows = [dict(r._mapping) for r in result]
    for row in rows:
        items_q = db.execute(text("""
            SELECT di.*, p.name as product_name,
                   di.qty * di.price as amount,
                   di.qty * di.price * di.vat_rate / 100 as vat_amount
            FROM document_items di
            JOIN products p ON p.id = di.product_id
            WHERE di.document_id = :did
        """), {"did": row["id"]})
        row["items"] = [dict(i._mapping) for i in items_q]
    return rows


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = db.execute(text("""
        SELECT d.*, cp.name as counterparty_name, w.name as warehouse_name
        FROM documents d
        LEFT JOIN counterparties cp ON cp.id = d.counterparty_id
        LEFT JOIN warehouses w ON w.id = d.warehouse_id
        WHERE d.id = :id
    """), {"id": doc_id})
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Документ не найден")
    doc = dict(row)
    items_q = db.execute(text("""
        SELECT di.*, p.name as product_name,
               di.qty * di.price as amount,
               di.qty * di.price * di.vat_rate / 100 as vat_amount
        FROM document_items di
        JOIN products p ON p.id = di.product_id
        WHERE di.document_id = :did
    """), {"did": doc_id})
    doc["items"] = [dict(i._mapping) for i in items_q]
    return doc


@router.post("/", response_model=MessageResponse, status_code=201)
def create_document(
    data: DocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "warehouse"))
):
    doc_data = data.model_dump(exclude={"items"})
    doc = Document(**doc_data)
    db.add(doc)
    db.flush()
    total = Decimal("0")
    total_vat = Decimal("0")
    for item_data in data.items:
        item = DocumentItem(document_id=doc.id, **item_data.model_dump())
        db.add(item)
        amount = item_data.qty * item_data.price
        vat = amount * item_data.vat_rate / Decimal("100")
        total += amount
        total_vat += vat
    doc.total_amount = total
    doc.total_vat = total_vat
    return {"message": "Документ создан", "id": doc.id}


@router.put("/{doc_id}", response_model=MessageResponse)
def update_document(
    doc_id: int,
    data: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "warehouse"))
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Документ не найден")

    was_confirmed = doc.status == "confirmed"
    old_counterparty_id = doc.counterparty_id

    if data.doc_date is not None:
        doc.doc_date = data.doc_date
    if data.counterparty_id is not None:
        doc.counterparty_id = data.counterparty_id
    if data.warehouse_id is not None:
        doc.warehouse_id = data.warehouse_id
    if data.notes is not None:
        doc.notes = data.notes
    if data.status is not None:
        doc.status = data.status

    if data.items is not None:
        db.query(DocumentItem).filter(DocumentItem.document_id == doc_id).delete()
        total = Decimal("0")
        total_vat = Decimal("0")
        for item_data in data.items:
            item = DocumentItem(document_id=doc.id, **item_data.model_dump())
            db.add(item)
            amount = item_data.qty * item_data.price
            vat = amount * item_data.vat_rate / Decimal("100")
            total += amount
            total_vat += vat
        doc.total_amount = total
        doc.total_vat = total_vat

    db.flush()

    # Пересчёт остатков
    recalculate_stock(db)

    # Полный пересчёт баланса контрагента
    if was_confirmed:
        if old_counterparty_id:
            recalculate_counterparty_balance(db, old_counterparty_id)
        if doc.counterparty_id and doc.counterparty_id != old_counterparty_id:
            recalculate_counterparty_balance(db, doc.counterparty_id)

    return {"message": "Документ обновлён", "id": doc_id}


@router.put("/{doc_id}/confirm", response_model=MessageResponse)
def confirm_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "warehouse"))
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Документ не найден")
    if doc.status == "confirmed":
        raise HTTPException(400, "Документ уже проведён")
    if doc.status == "cancelled":
        raise HTTPException(400, "Нельзя провести отменённый документ")
    doc.status = "confirmed"
    db.flush()

    recalculate_stock(db)
    if doc.counterparty_id:
        recalculate_counterparty_balance(db, doc.counterparty_id)

    return {"message": "Документ проведён", "id": doc_id}


@router.put("/{doc_id}/cancel", response_model=MessageResponse)
def cancel_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "warehouse"))
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Документ не найден")
    if doc.status != "confirmed":
        raise HTTPException(400, "Можно отменить только проведённый документ")
    doc.status = "draft"
    db.flush()

    recalculate_stock(db)
    if doc.counterparty_id:
        recalculate_counterparty_balance(db, doc.counterparty_id)

    return {"message": "Проведение документа отменено", "id": doc_id}


@router.delete("/{doc_id}", response_model=MessageResponse)
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Документ не найден")
    if doc.status == "confirmed":
        raise HTTPException(400, "Нельзя удалить проведённый документ")
    db.delete(doc)
    return {"message": "Документ удалён"}
