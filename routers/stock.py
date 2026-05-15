from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from models import User
from routers.auth import get_current_user, require_role
from typing import Optional

router = APIRouter()

RECALC_SQL = """
    INSERT INTO stock (sort_id, warehouse_id, qty)
    SELECT
        di.sort_id,
        d.warehouse_id,
        SUM(di.qty * CASE d.doc_type
            WHEN 'receipt'    THEN  1
            WHEN 'shipment'   THEN -1
            WHEN 'return_in'  THEN  1
            WHEN 'return_out' THEN -1
            WHEN 'writeoff'   THEN -1
            ELSE 0
        END)
    FROM document_items di
    JOIN documents d ON d.id = di.document_id
    WHERE d.status = 'confirmed'
      AND d.warehouse_id IS NOT NULL
      AND di.sort_id IS NOT NULL
    GROUP BY di.sort_id, d.warehouse_id
    ON CONFLICT (sort_id, warehouse_id) DO UPDATE SET qty = EXCLUDED.qty
"""

@router.get("/")
def list_stock(
    warehouse_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = "SELECT * FROM v_stock_alerts WHERE 1=1"
    params = {}
    if warehouse_id:
        query += " AND warehouse_id = :wh"
        params["wh"] = warehouse_id
    query += " ORDER BY category_name, sort_name"
    result = db.execute(text(query), params)
    return [dict(r._mapping) for r in result]

@router.get("/alerts")
def stock_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = db.execute(text("""
        SELECT * FROM v_stock_alerts
        WHERE qty <= 0
        ORDER BY category_name, sort_name
    """))
    return [dict(r._mapping) for r in result]

@router.post("/recalculate")
def recalculate_stock(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "warehouse"))
):
    db.execute(text("DELETE FROM stock"))
    db.execute(text(RECALC_SQL))
    return {"message": "Остатки пересчитаны"}
