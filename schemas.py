from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from models import DocTypeEnum, DocStatusEnum, TxnTypeEnum, CounterpartyTypeEnum, AccountTypeEnum

# ── ЕДИНИЦЫ ──────────────────────────────────────────────────

class UnitBase(BaseModel):
    name: str
    short_name: str
    is_active: bool = True

class UnitCreate(UnitBase): pass
class UnitUpdate(UnitBase): pass
class UnitOut(UnitBase):
    id: int
    class Config: from_attributes = True

# ── КАТЕГОРИИ ТОВАРОВ ─────────────────────────────────────────

class ProductCategoryBase(BaseModel):
    name: str
    is_active: bool = True

class ProductCategoryCreate(ProductCategoryBase): pass
class ProductCategoryUpdate(ProductCategoryBase): pass
class ProductCategoryOut(ProductCategoryBase):
    id: int
    class Config: from_attributes = True

# ── СОРТА ТОВАРОВ ─────────────────────────────────────────────

class ProductSortBase(BaseModel):
    name: str
    category_id: int
    is_active: bool = True

class ProductSortCreate(ProductSortBase): pass
class ProductSortUpdate(ProductSortBase): pass
class ProductSortOut(ProductSortBase):
    id: int
    category_name: Optional[str] = None
    class Config: from_attributes = True

# ── СТРАНЫ ────────────────────────────────────────────────────

class CountryBase(BaseModel):
    name: str
    is_active: bool = True

class CountryCreate(CountryBase): pass
class CountryUpdate(CountryBase): pass
class CountryOut(CountryBase):
    id: int
    class Config: from_attributes = True

# ── СКЛАДЫ ────────────────────────────────────────────────────

class WarehouseBase(BaseModel):
    name: str
    address: Optional[str] = None
    is_active: bool = True

class WarehouseCreate(WarehouseBase): pass
class WarehouseOut(WarehouseBase):
    id: int
    class Config: from_attributes = True

# ── СЧЕТА ─────────────────────────────────────────────────────

class AccountBase(BaseModel):
    name: str
    type: AccountTypeEnum
    currency: str = "RUB"
    bank_name: Optional[str] = None
    account_no: Optional[str] = None
    is_active: bool = True

class AccountCreate(AccountBase): pass
class AccountUpdate(AccountBase): pass
class AccountOut(AccountBase):
    id: int
    balance: Decimal
    class Config: from_attributes = True

# ── КОНТРАГЕНТЫ ───────────────────────────────────────────────

class CounterpartyBase(BaseModel):
    name: str
    type: CounterpartyTypeEnum
    legal_type: Optional[str] = None
    inn: Optional[str] = None
    kpp: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    credit_limit: Decimal = Decimal("0")
    notes: Optional[str] = None
    is_active: bool = True

class CounterpartyCreate(CounterpartyBase): pass
class CounterpartyUpdate(CounterpartyBase): pass
class CounterpartyOut(CounterpartyBase):
    id: int
    balance: Decimal
    created_at: datetime
    class Config: from_attributes = True

# ── ОСТАТКИ ───────────────────────────────────────────────────

class StockOut(BaseModel):
    id: int
    category_id: int
    sort_id: Optional[int] = None
    warehouse_id: int
    qty: Decimal
    updated_at: datetime
    category_name: Optional[str] = None
    sort_name: Optional[str] = None
    warehouse: Optional[str] = None
    class Config: from_attributes = True

# ── ДОКУМЕНТЫ ─────────────────────────────────────────────────

class DocumentItemBase(BaseModel):
    category_id: Optional[int] = None
    sort_id: Optional[int] = None
    qty: Decimal
    price: Decimal
    vat_rate: Decimal = Decimal("20")
    unit_id: Optional[int] = None
    country_id: Optional[int] = None

class DocumentItemCreate(DocumentItemBase): pass
class DocumentItemOut(DocumentItemBase):
    id: int
    amount: Optional[Decimal] = None
    vat_amount: Optional[Decimal] = None
    sort_name: Optional[str] = None
    category_name: Optional[str] = None
    unit_name: Optional[str] = None
    country_name: Optional[str] = None
    class Config: from_attributes = True

class DocumentBase(BaseModel):
    doc_number: str
    doc_type: DocTypeEnum
    doc_date: date
    counterparty_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    warehouse_to_id: Optional[int] = None
    notes: Optional[str] = None

class DocumentCreate(DocumentBase):
    items: List[DocumentItemCreate] = []

class DocumentUpdate(BaseModel):
    doc_date: Optional[date] = None
    counterparty_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    notes: Optional[str] = None
    status: Optional[DocStatusEnum] = None
    items: Optional[List[DocumentItemCreate]] = None

class DocumentOut(DocumentBase):
    id: int
    status: DocStatusEnum
    total_amount: Decimal
    total_vat: Decimal
    created_at: datetime
    items: List[DocumentItemOut] = []
    counterparty_name: Optional[str] = None
    warehouse_name: Optional[str] = None
    class Config: from_attributes = True

# ── ФИНАНСЫ ───────────────────────────────────────────────────

class TransactionBase(BaseModel):
    txn_date: date
    txn_type: TxnTypeEnum
    account_id: int
    account_to_id: Optional[int] = None
    amount: Decimal
    counterparty_id: Optional[int] = None
    document_id: Optional[int] = None
    category: Optional[str] = None
    description: str

class TransactionCreate(TransactionBase): pass

class TransactionUpdate(BaseModel):
    txn_date: Optional[date] = None
    txn_type: Optional[TxnTypeEnum] = None
    account_id: Optional[int] = None
    account_to_id: Optional[int] = None
    amount: Optional[Decimal] = None
    counterparty_id: Optional[int] = None
    document_id: Optional[int] = None
    category: Optional[str] = None
    description: Optional[str] = None

class TransactionOut(TransactionBase):
    id: int
    status: str = "draft"
    created_at: datetime
    counterparty_name: Optional[str] = None
    account_name: Optional[str] = None
    class Config: from_attributes = True

# ── ОБЩИЕ ─────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
    id: Optional[int] = None
