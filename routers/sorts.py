from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db
from models import ProductSort, ProductCategory, User
from schemas import ProductSortCreate, ProductSortUpdate, ProductSortOut, MessageResponse
from routers.auth import get_current_user, require_role
from typing import List

router = APIRouter()


@router.get("/", response_model=List[ProductSortOut])
def list_sorts(
    active_only: bool = True,
    category_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = db.execute(text("""
        SELECT s.*, c.name as category_name
        FROM product_sorts s
        JOIN product_categories c ON c.id = s.category_id
        WHERE (:active_only = FALSE OR s.is_active = TRUE)
          AND (:category_id IS NULL OR s.category_id = :category_id)
        ORDER BY c.name, s.name
    """), {"active_only": active_only, "category_id": category_id})
    return [dict(r._mapping) for r in result]


@router.get("/{sort_id}", response_model=ProductSortOut)
def get_sort(
    sort_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = db.execute(text("""
        SELECT s.*, c.name as category_name
        FROM product_sorts s
        JOIN product_categories c ON c.id = s.category_id
        WHERE s.id = :id
    """), {"id": sort_id})
    row = result.mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Сорт не найден")
    return dict(row)


@router.post("/", response_model=MessageResponse, status_code=201)
def create_sort(
    data: ProductSortCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    cat = db.query(ProductCategory).filter(ProductCategory.id == data.category_id).first()
    if not cat:
        raise HTTPException(404, "Товар не найден")
    s = ProductSort(name=data.name, category_id=data.category_id, is_active=data.is_active)
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"message": "Сорт создан", "id": s.id}


@router.put("/{sort_id}", response_model=MessageResponse)
def update_sort(
    sort_id: int,
    data: ProductSortUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    s = db.query(ProductSort).filter(ProductSort.id == sort_id).first()
    if not s:
        raise HTTPException(404, "Сорт не найден")
    cat = db.query(ProductCategory).filter(ProductCategory.id == data.category_id).first()
    if not cat:
        raise HTTPException(404, "Товар не найден")
    s.name = data.name
    s.category_id = data.category_id
    s.is_active = data.is_active
    return {"message": "Сорт обновлён", "id": sort_id}


@router.delete("/{sort_id}", response_model=MessageResponse)
def deactivate_sort(
    sort_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    s = db.query(ProductSort).filter(ProductSort.id == sort_id).first()
    if not s:
        raise HTTPException(404, "Сорт не найден")
    s.is_active = False
    return {"message": "Сорт деактивирован", "id": sort_id}
