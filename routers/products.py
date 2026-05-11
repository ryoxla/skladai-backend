from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from models import Product, User
from schemas import ProductCreate, ProductUpdate, ProductOut, ProductWithStock, MessageResponse
from routers.auth import get_current_user, require_role
from typing import List, Optional

router = APIRouter()

@router.get("/", response_model=List[ProductWithStock])
def list_products(
    active_only: bool = True,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = """
        SELECT p.*, COALESCE(SUM(s.qty),0) as qty, u.short_name as unit_name,
               CASE WHEN COALESCE(SUM(s.qty),0) = 0 THEN 'out_of_stock'
                    WHEN COALESCE(SUM(s.qty),0) <= p.min_qty THEN 'low_stock'
                    ELSE 'ok' END as alert
        FROM products p
        LEFT JOIN stock s ON s.product_id = p.id
        LEFT JOIN units u ON u.id = p.unit_id
        WHERE 1=1
    """
    params = {}
    if active_only:
        query += " AND p.is_active = true"
    if search:
        query += " AND (p.name ILIKE :s OR p.sku ILIKE :s)"
        params["s"] = f"%{search}%"
    query += " GROUP BY p.id, u.short_name ORDER BY p.name"
    result = db.execute(text(query), params)
    return [dict(r._mapping) for r in result]

@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(404, "Товар не найден")
    return p

@router.post("/", response_model=MessageResponse, status_code=201)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "warehouse"))
):
    p = Product(**data.model_dump())
    db.add(p)
    db.flush()
    return {"message": "Товар создан", "id": p.id}

@router.put("/{product_id}", response_model=MessageResponse)
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager", "warehouse"))
):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(404, "Товар не найден")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    return {"message": "Товар обновлён", "id": p.id}

@router.delete("/{product_id}", response_model=MessageResponse)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(404, "Товар не найден")
    p.is_active = False
    return {"message": "Товар деактивирован", "id": product_id}
