-- schema_clean.sql — полная схема БД складAI (актуальная)
-- Обновлено: удалена таблица products, stock использует sort_id,
-- document_items без product_id, добавлены актуальные views

-- ── ПОЛЬЗОВАТЕЛИ ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    email         VARCHAR(100) NOT NULL UNIQUE,
    password_hash TEXT         NOT NULL,
    full_name     VARCHAR(150),
    role          VARCHAR(20)  NOT NULL DEFAULT 'viewer',
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    last_login    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  DEFAULT NOW()
);

-- ── ЕДИНИЦЫ ИЗМЕРЕНИЯ ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS units (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(50)  NOT NULL,
    short_name VARCHAR(10)  NOT NULL UNIQUE,
    is_active  BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ  DEFAULT NOW()
);

-- ── ТОВАРЫ (справочник, ранее: категории товаров) ─────────────

CREATE TABLE IF NOT EXISTS product_categories (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    parent_id  INTEGER REFERENCES product_categories(id),
    is_active  BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ  DEFAULT NOW()
);

-- ── СОРТА ТОВАРОВ (привязаны к товару через category_id) ──────

CREATE TABLE IF NOT EXISTS product_sorts (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    category_id INTEGER      NOT NULL REFERENCES product_categories(id),
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- ── СТРАНЫ ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS countries (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100) NOT NULL UNIQUE,
    is_active  BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ  DEFAULT NOW()
);

-- ── СКЛАДЫ ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS warehouses (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    address    TEXT,
    is_active  BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ  DEFAULT NOW()
);

-- ── СЧЕТА / КАССЫ ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS accounts (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    type       VARCHAR(10)  NOT NULL,   -- cash | bank | card
    currency   VARCHAR(3)   DEFAULT 'RUB',
    balance    NUMERIC(15,2) DEFAULT 0,
    bank_name  VARCHAR(100),
    account_no VARCHAR(30),
    is_active  BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ  DEFAULT NOW()
);

-- ── КОНТРАГЕНТЫ ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS counterparties (
    id           SERIAL PRIMARY KEY,
    name         VARCHAR(255) NOT NULL,
    type         VARCHAR(10)  NOT NULL,  -- client | supplier | both
    legal_type   VARCHAR(20),
    inn          VARCHAR(12)  UNIQUE,
    kpp          VARCHAR(9),
    phone        VARCHAR(20),
    email        VARCHAR(100),
    address      TEXT,
    contact_name VARCHAR(150),
    credit_limit NUMERIC(15,2) DEFAULT 0,
    balance      NUMERIC(15,2) DEFAULT 0,
    notes        TEXT,
    is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ  DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  DEFAULT NOW()
);

-- ── ОСТАТКИ ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS stock (
    id           SERIAL PRIMARY KEY,
    sort_id      INTEGER       NOT NULL REFERENCES product_sorts(id),
    warehouse_id INTEGER       NOT NULL REFERENCES warehouses(id),
    qty          NUMERIC(15,3) DEFAULT 0,
    updated_at   TIMESTAMPTZ   DEFAULT NOW(),
    UNIQUE (sort_id, warehouse_id)
);

-- ── ДОКУМЕНТЫ ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS documents (
    id              SERIAL PRIMARY KEY,
    doc_number      VARCHAR(30)  NOT NULL UNIQUE,
    doc_type        VARCHAR(20)  NOT NULL,  -- receipt|shipment|return_in|return_out|transfer|inventory|writeoff
    doc_date        DATE         NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'draft',  -- draft|confirmed|cancelled
    counterparty_id INTEGER REFERENCES counterparties(id),
    warehouse_id    INTEGER REFERENCES warehouses(id),
    warehouse_to_id INTEGER REFERENCES warehouses(id),
    total_amount    NUMERIC(15,2) DEFAULT 0,
    total_vat       NUMERIC(15,2) DEFAULT 0,
    notes           TEXT,
    created_by      INTEGER,
    confirmed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── ПОЗИЦИИ ДОКУМЕНТА ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS document_items (
    id          SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    sort_id     INTEGER REFERENCES product_sorts(id),
    qty         NUMERIC(15,3) NOT NULL,
    price       NUMERIC(15,2) DEFAULT 0,
    vat_rate    NUMERIC(5,2)  DEFAULT 20,
    unit_id     INTEGER REFERENCES units(id),
    country_id  INTEGER REFERENCES countries(id)
);

-- ── ФИНАНСЫ ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS transactions (
    id              SERIAL PRIMARY KEY,
    txn_date        DATE        NOT NULL,
    txn_type        VARCHAR(10) NOT NULL,  -- income | expense | transfer
    status          VARCHAR(20) NOT NULL DEFAULT 'draft',  -- draft | confirmed
    account_id      INTEGER     NOT NULL REFERENCES accounts(id),
    account_to_id   INTEGER REFERENCES accounts(id),
    amount          NUMERIC(15,2) NOT NULL,
    counterparty_id INTEGER REFERENCES counterparties(id),
    document_id     INTEGER REFERENCES documents(id),
    category        VARCHAR(100),
    description     TEXT        NOT NULL,
    created_by      INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── ПРЕДСТАВЛЕНИЯ (VIEWS) ─────────────────────────────────────

CREATE OR REPLACE VIEW v_stock_alerts AS
SELECT
    s.id,
    s.sort_id,
    s.warehouse_id,
    ps.name AS sort_name,
    pc.name AS category_name,
    w.name  AS warehouse_name,
    s.qty,
    CASE
        WHEN s.qty <= 0 THEN 'out_of_stock'
        ELSE 'ok'
    END AS alert_level,
    s.updated_at
FROM stock s
JOIN product_sorts ps      ON ps.id = s.sort_id
JOIN product_categories pc ON pc.id = ps.category_id
JOIN warehouses w          ON w.id  = s.warehouse_id
WHERE ps.is_active = true;

CREATE OR REPLACE VIEW v_counterparty_balances AS
SELECT
    id,
    name,
    type,
    balance,
    is_active
FROM counterparties
WHERE is_active = true;

CREATE OR REPLACE VIEW v_cashflow_monthly AS
SELECT
    DATE_TRUNC('month', txn_date) AS month,
    SUM(CASE WHEN txn_type = 'income'  THEN amount ELSE 0 END) AS income,
    SUM(CASE WHEN txn_type = 'expense' THEN amount ELSE 0 END) AS expense
FROM transactions
WHERE status = 'confirmed'
GROUP BY 1
ORDER BY 1 DESC;
