from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Country, User
from schemas import CountryCreate, CountryUpdate, CountryOut, MessageResponse
from routers.auth import get_current_user, require_role
from typing import List

router = APIRouter()


@router.get("/", response_model=List[CountryOut])
def list_countries(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    q = db.query(Country)
    if active_only:
        q = q.filter(Country.is_active == True)
    return q.order_by(Country.name).all()


@router.get("/{country_id}", response_model=CountryOut)
def get_country(
    country_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    c = db.query(Country).filter(Country.id == country_id).first()
    if not c:
        raise HTTPException(404, "Страна не найдена")
    return c


@router.post("/", response_model=MessageResponse, status_code=201)
def create_country(
    data: CountryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    existing = db.query(Country).filter(Country.name == data.name).first()
    if existing:
        raise HTTPException(400, "Страна с таким названием уже существует")
    c = Country(name=data.name, is_active=data.is_active)
    db.add(c)
    db.flush()
    return {"message": "Страна добавлена", "id": c.id}


@router.put("/{country_id}", response_model=MessageResponse)
def update_country(
    country_id: int,
    data: CountryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    c = db.query(Country).filter(Country.id == country_id).first()
    if not c:
        raise HTTPException(404, "Страна не найдена")
    existing = db.query(Country).filter(Country.name == data.name, Country.id != country_id).first()
    if existing:
        raise HTTPException(400, "Страна с таким названием уже существует")
    c.name = data.name
    c.is_active = data.is_active
    return {"message": "Страна обновлена", "id": country_id}


@router.delete("/{country_id}", response_model=MessageResponse)
def deactivate_country(
    country_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager"))
):
    c = db.query(Country).filter(Country.id == country_id).first()
    if not c:
        raise HTTPException(404, "Страна не найдена")
    c.is_active = False
    return {"message": "Страна деактивирована", "id": country_id}
