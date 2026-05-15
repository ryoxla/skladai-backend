from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from models import User
from routers.auth import get_current_user, require_role
from routers.utils import RECALC_SQL
from typing import Optional

router = APIRouter()

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
