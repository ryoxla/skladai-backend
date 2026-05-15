import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from decimal import Decimal
from database import get_db
from models import Document, DocumentItem, Counterparty, User, ProductSort, ProductCategory, Stock
from schemas import DocumentCreate, DocumentUpdate, DocumentOut, MessageResponse
from routers.auth import get_current_user, require_role
from routers.utils import RECALC_SQL
from typing import List, Optional
from datetime import date, datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter()

ITEMS_SQL = """
    SELECT di.*,
           ps.name as sort_name,
           pc.name as category_name,
           u.short_name as unit_name,
           c.name as country_name,
           di.qty * di.price as amount,
           di.qty * di.price * di.vat_rate / 100 as vat_amount
    FROM document_items di
    LEFT JOIN product_sorts ps ON ps.id = di.sort_id
    LEFT JOIN product_categories pc ON pc.id = ps.category_id
    LEFT JOIN units u ON u.id = di.unit_id
    LEFT JOIN countries c ON c.id = di.country_id
    WHERE di.document_id = :did
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
        items_q = db.execute(text(ITEMS_SQL), {"did": row["id"]})
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
    items_q = db.execute(text(ITEMS_SQL), {"did": doc_id})
    doc["items"] = [dict(i._mapping) for i in items_q]
    return doc


@router.post("/", response_model=MessageResponse, status_code=201)
def create_document(
    data: DocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "warehouse"))
):
    if data.counterparty_id:
        cp = db.query(Counterparty).filter(
            Counterparty.id == data.counterparty_id,
            Counterparty.is_active == True
        ).first()
        if not cp:
            raise HTTPException(400, "Контрагент не активен или не найден")
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

    if doc.doc_type in ('shipment', 'return_out', 'writeoff'):
        items = db.query(DocumentItem).filter(
            DocumentItem.document_id == doc_id
        ).all()
        errors = []
        for item in items:
            cat_id = item.category_id
            if not cat_id and item.sort_id:
                sort = db.query(ProductSort).filter(
                    ProductSort.id == item.sort_id
                ).first()
                cat_id = sort.category_id if sort else None
            if not cat_id:
                continue
            stock_qty = db.execute(text("""
                SELECT qty FROM stock
                WHERE category_id = :cat_id
                  AND warehouse_id = :wh_id
                  AND (
                    (sort_id = :sort_id) OR
                    (sort_id IS NULL AND :sort_id IS NULL)
                  )
            """), {
                "cat_id": cat_id,
                "wh_id": doc.warehouse_id,
                "sort_id": item.sort_id
            }).scalar() or 0

            if item.qty > stock_qty:
                sort_name = ""
                if item.sort_id:
                    s = db.query(ProductSort).filter(
                        ProductSort.id == item.sort_id
                    ).first()
                    sort_name = f" ({s.name})" if s else ""
                cat = db.query(ProductCategory).filter(
                    ProductCategory.id == cat_id
                ).first()
                cat_name = cat.name if cat else str(cat_id)
                errors.append(
                    f"{cat_name}{sort_name}: запрошено {item.qty}, доступно {stock_qty}"
                )
        if errors:
            raise HTTPException(400,
                "Недостаточно остатков: " + "; ".join(errors)
            )

    try:
        doc.status = "confirmed"
        doc.confirmed_at = datetime.now(timezone.utc)
        db.flush()
    except Exception as e:
        logger.error("confirm_document flush error doc_id=%s: %s", doc_id, e, exc_info=True)
        raise HTTPException(500, f"Ошибка при сохранении статуса документа: {e}")

    try:
        recalculate_stock(db)
    except Exception as e:
        logger.error("confirm_document recalculate_stock error doc_id=%s: %s", doc_id, e, exc_info=True)
        raise HTTPException(500, f"Ошибка пересчёта остатков: {e}")

    try:
        if doc.counterparty_id:
            recalculate_counterparty_balance(db, doc.counterparty_id)
    except Exception as e:
        logger.error("confirm_document balance error doc_id=%s cp_id=%s: %s", doc_id, doc.counterparty_id, e, exc_info=True)
        raise HTTPException(500, f"Ошибка пересчёта баланса контрагента: {e}")

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
