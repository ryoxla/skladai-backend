from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, contains_eager
from sqlalchemy import text
from database import get_db
from models import ProductSort, ProductCategory, User
from schemas import ProductSortCreate, ProductSortUpdate, ProductSortOut, MessageResponse
from routers.auth import get_current_user, require_role
from typing import List, Optional

router = APIRouter()


@router.get("/", response_model=List[ProductSortOut])
def list_sorts(
    active_only: bool = True,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    q = (
        db.query(ProductSort)
        .join(ProductSort.category)
        .options(contains_eager(ProductSort.category))
    )
    if active_only:
        q = q.filter(ProductSort.is_active == True)
    if category_id is not None:
        q = q.filter(ProductSort.category_id == category_id)
    q = q.order_by(ProductCategory.name, ProductSort.name)
    return [
        {
            "id": s.id,
            "name": s.name,
            "category_id": s.category_id,
            "is_active": s.is_active,
            "category_name": s.category.name if s.category else None,
        }
        for s in q.all()
    ]


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
    db.flush()
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
