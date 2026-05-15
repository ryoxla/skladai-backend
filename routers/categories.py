from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import ProductCategory, ProductSort, User
from schemas import (
    ProductCategoryCreate, ProductCategoryUpdate, ProductCategoryOut,
    ProductSortOut, MessageResponse
)
from routers.auth import get_current_user, require_role
from typing import List

router = APIRouter()


@router.get("/", response_model=List[ProductCategoryOut])
def list_categories(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    q = db.query(ProductCategory)
    if active_only:
        q = q.filter(ProductCategory.is_active == True)
    return q.order_by(ProductCategory.name).all()


@router.get("/{category_id}", response_model=ProductCategoryOut)
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cat = db.query(ProductCategory).filter(ProductCategory.id == category_id).first()
    if not cat:
        raise HTTPException(404, "Товар не найден")
    return cat


@router.get("/{category_id}/sorts", response_model=List[ProductSortOut])
def get_sorts_by_category(
    category_id: int,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    q = db.query(ProductSort).filter(ProductSort.category_id == category_id)
    if active_only:
        q = q.filter(ProductSort.is_active == True)
    return q.order_by(ProductSort.name).all()


@router.post("/", response_model=MessageResponse, status_code=201)
def create_category(
    data: ProductCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    cat = ProductCategory(name=data.name, is_active=data.is_active)
    db.add(cat)
    db.flush()
    return {"message": "Товар создан", "id": cat.id}


@router.put("/{category_id}", response_model=MessageResponse)
def update_category(
    category_id: int,
    data: ProductCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    cat = db.query(ProductCategory).filter(ProductCategory.id == category_id).first()
    if not cat:
        raise HTTPException(404, "Товар не найден")
    cat.name = data.name
    cat.is_active = data.is_active
    return {"message": "Товар обновлён", "id": category_id}


@router.delete("/{category_id}", response_model=MessageResponse)
def deactivate_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    cat = db.query(ProductCategory).filter(ProductCategory.id == category_id).first()
    if not cat:
        raise HTTPException(404, "Товар не найден")
    active_sorts = db.query(ProductSort).filter(
        ProductSort.category_id == category_id,
        ProductSort.is_active == True
    ).count()
    if active_sorts > 0:
        raise HTTPException(400, f"Нельзя деактивировать товар: есть {active_sorts} активных сортов")
    cat.is_active = False
    return {"message": "Товар деактивирован", "id": category_id}
