from sqlalchemy import Column, Integer, String, Numeric, Boolean, Text, Date, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum

class DocTypeEnum(str, enum.Enum):
    receipt    = "receipt"
    shipment   = "shipment"
    return_in  = "return_in"
    return_out = "return_out"
    transfer   = "transfer"
    inventory  = "inventory"
    writeoff   = "writeoff"

class DocStatusEnum(str, enum.Enum):
    draft     = "draft"
    confirmed = "confirmed"
    cancelled = "cancelled"

class TxnTypeEnum(str, enum.Enum):
    income   = "income"
    expense  = "expense"
    transfer = "transfer"

class CounterpartyTypeEnum(str, enum.Enum):
    client   = "client"
    supplier = "supplier"
    both     = "both"

class AccountTypeEnum(str, enum.Enum):
    cash = "cash"
    bank = "bank"
    card = "card"

# ── СПРАВОЧНИКИ ──────────────────────────────────────────────

class Unit(Base):
    __tablename__ = "units"
    id         = Column(Integer, primary_key=True)
    name       = Column(String(50), nullable=False)
    short_name = Column(String(10), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ProductCategory(Base):
    __tablename__ = "product_categories"
    id        = Column(Integer, primary_key=True)
    name      = Column(String(100), nullable=False)
    parent_id = Column(Integer, ForeignKey("product_categories.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Warehouse(Base):
    __tablename__ = "warehouses"
    id         = Column(Integer, primary_key=True)
    name       = Column(String(100), nullable=False)
    address    = Column(Text)
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Account(Base):
    __tablename__ = "accounts"
    id         = Column(Integer, primary_key=True)
    name       = Column(String(100), nullable=False)
    type       = Column(SAEnum(AccountTypeEnum), nullable=False)
    currency   = Column(String(3), default="RUB")
    balance    = Column(Numeric(15, 2), default=0)
    bank_name  = Column(String(100))
    account_no = Column(String(30))
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# ── КОНТРАГЕНТЫ ───────────────────────────────────────────────

class Counterparty(Base):
    __tablename__ = "counterparties"
    id           = Column(Integer, primary_key=True)
    name         = Column(String(255), nullable=False)
    type         = Column(SAEnum(CounterpartyTypeEnum), nullable=False)
    legal_type   = Column(String(20))
    inn          = Column(String(12), unique=True)
    kpp          = Column(String(9))
    phone        = Column(String(20))
    email        = Column(String(100))
    address      = Column(Text)
    contact_name = Column(String(150))
    credit_limit = Column(Numeric(15, 2), default=0)
    balance      = Column(Numeric(15, 2), default=0)
    notes        = Column(Text)
    is_active    = Column(Boolean, default=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), server_default=func.now())

# ── ТОВАРЫ ────────────────────────────────────────────────────

class Product(Base):
    __tablename__ = "products"
    id          = Column(Integer, primary_key=True)
    name        = Column(String(255), nullable=False)
    sku         = Column(String(50), nullable=False, unique=True)
    sort        = Column(String(100))
    country     = Column(String(100))
    category_id = Column(Integer, ForeignKey("product_categories.id"))
    unit_id     = Column(Integer, ForeignKey("units.id"), nullable=False)
    vat_rate    = Column(Numeric(5, 2), default=20)
    min_qty     = Column(Numeric(15, 3), default=0)
    description = Column(Text)
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), server_default=func.now())

class Stock(Base):
    __tablename__ = "stock"
    id           = Column(Integer, primary_key=True)
    product_id   = Column(Integer, ForeignKey("products.id"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    qty          = Column(Numeric(15, 3), default=0)
    updated_at   = Column(DateTime(timezone=True), server_default=func.now())

# ── ДОКУМЕНТЫ ─────────────────────────────────────────────────

class Document(Base):
    __tablename__ = "documents"
    id               = Column(Integer, primary_key=True)
    doc_number       = Column(String(30), nullable=False, unique=True)
    doc_type         = Column(SAEnum(DocTypeEnum), nullable=False)
    doc_date         = Column(Date, nullable=False)
    status           = Column(SAEnum(DocStatusEnum), default="draft")
    counterparty_id  = Column(Integer, ForeignKey("counterparties.id"))
    warehouse_id     = Column(Integer, ForeignKey("warehouses.id"))
    warehouse_to_id  = Column(Integer, ForeignKey("warehouses.id"))
    total_amount     = Column(Numeric(15, 2), default=0)
    total_vat        = Column(Numeric(15, 2), default=0)
    notes            = Column(Text)
    created_by       = Column(Integer)
    confirmed_at     = Column(DateTime(timezone=True))
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    updated_at       = Column(DateTime(timezone=True), server_default=func.now())
    items            = relationship("DocumentItem", back_populates="document", cascade="all, delete-orphan")

class DocumentItem(Base):
    __tablename__ = "document_items"
    id          = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    product_id  = Column(Integer, ForeignKey("products.id"), nullable=False)
    qty         = Column(Numeric(15, 3), nullable=False)
    price       = Column(Numeric(15, 2), default=0)
    vat_rate    = Column(Numeric(5, 2), default=20)
    document    = relationship("Document", back_populates="items")

# ── ФИНАНСЫ ───────────────────────────────────────────────────

class Transaction(Base):
    __tablename__ = "transactions"
    id               = Column(Integer, primary_key=True)
    txn_date         = Column(Date, nullable=False)
    txn_type         = Column(SAEnum(TxnTypeEnum), nullable=False)
    status           = Column(String(20), nullable=False, default="draft", server_default="draft")
    account_id       = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    account_to_id    = Column(Integer, ForeignKey("accounts.id"))
    amount           = Column(Numeric(15, 2), nullable=False)
    counterparty_id  = Column(Integer, ForeignKey("counterparties.id"))
    document_id      = Column(Integer, ForeignKey("documents.id"))
    category         = Column(String(100))
    description      = Column(Text, nullable=False)
    created_by       = Column(Integer)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())

class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True)
    username      = Column(String(50), nullable=False, unique=True)
    email         = Column(String(100), nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    full_name     = Column(String(150))
    role          = Column(String(20), nullable=False, default="viewer")
    is_active     = Column(Boolean, default=True)
    last_login    = Column(DateTime(timezone=True))
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
