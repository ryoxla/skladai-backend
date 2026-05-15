from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv
import os
import logging

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:123@localhost:5432/skladai"
).replace("postgresql+psycopg2://", "postgresql+psycopg://").replace("postgresql://", "postgresql+psycopg://")

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run_migrations():
    """Apply pending database migrations on startup.

    Migration 002 adds the `status` column to `transactions`.
    This was introduced in PR #9 and must be applied before the
    recalculate_* helpers can query `WHERE status = 'confirmed'`.
    Using ADD COLUMN IF NOT EXISTS so it is safe to run every time.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE transactions "
                "ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'confirmed'"
            ))
            conn.execute(text(
                "ALTER TABLE transactions ALTER COLUMN status SET DEFAULT 'draft'"
            ))
            conn.commit()
        logger.info("Migration 002 (transactions.status) applied successfully")
    except Exception as e:
        logger.warning("Migration 002 skipped or failed (may be harmless): %s", e)

    for _sql, _label in [
        (
            "ALTER TABLE product_categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
            "003a product_categories.is_active",
        ),
        (
            "ALTER TABLE units ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
            "003b units.is_active",
        ),
        (
            """CREATE TABLE IF NOT EXISTS product_sorts (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    category_id INTEGER NOT NULL REFERENCES product_categories(id),
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )""",
            "003c product_sorts table",
        ),
        (
            """CREATE TABLE IF NOT EXISTS countries (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )""",
            "003d countries table",
        ),
        (
            "ALTER TABLE document_items ADD COLUMN IF NOT EXISTS unit_id INTEGER REFERENCES units(id)",
            "003e document_items.unit_id",
        ),
        (
            "ALTER TABLE document_items ADD COLUMN IF NOT EXISTS country_id INTEGER REFERENCES countries(id)",
            "003f document_items.country_id",
        ),
    ]:
        try:
            with engine.connect() as conn:
                conn.execute(text(_sql))
                conn.commit()
            logger.info("Migration %s applied successfully", _label)
        except Exception as e:
            logger.warning("Migration %s skipped or failed (may be harmless): %s", _label, e)

    try:
        with engine.connect() as conn:
            conn.execute(text("""
                UPDATE counterparties cp
                SET balance = (
                    SELECT COALESCE(SUM(CASE doc_type
                        WHEN 'receipt'    THEN total_amount
                        WHEN 'return_in'  THEN -total_amount
                        WHEN 'shipment'   THEN -total_amount
                        WHEN 'return_out' THEN total_amount
                        ELSE 0
                    END), 0)
                    FROM documents
                    WHERE counterparty_id = cp.id AND status = 'confirmed'
                ) + (
                    SELECT COALESCE(SUM(CASE txn_type
                        WHEN 'income'  THEN  amount
                        WHEN 'expense' THEN -amount
                        ELSE 0
                    END), 0)
                    FROM transactions
                    WHERE counterparty_id = cp.id AND status = 'confirmed'
                )
            """))
            conn.commit()
        logger.info("Migration 003 (recalculate counterparty balances) applied successfully")
    except Exception as e:
        logger.warning("Migration 003 skipped or failed (may be harmless): %s", e)

    try:
        with engine.connect() as conn:
            conn.execute(text("COMMENT ON TABLE product_categories IS 'Справочник товаров'"))
            conn.execute(text("COMMENT ON TABLE product_sorts IS 'Справочник сортов товаров'"))
            conn.execute(text("COMMENT ON COLUMN product_sorts.category_id IS 'ID товара'"))
            conn.commit()
        logger.info("Migration 004 (rename category→product comments) applied successfully")
    except Exception as e:
        logger.warning("Migration 004 skipped or failed (may be harmless): %s", e)

    try:
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE document_items ALTER COLUMN product_id DROP NOT NULL"
            ))
            conn.execute(text(
                "ALTER TABLE document_items ADD COLUMN IF NOT EXISTS sort_id INTEGER REFERENCES product_sorts(id)"
            ))
            conn.commit()
        logger.info("Migration 005 (document_items sort_id, nullable product_id) applied successfully")
    except Exception as e:
        logger.warning("Migration 005 skipped or failed (may be harmless): %s", e)

    for _sql, _label in [
        ("DROP TRIGGER IF EXISTS update_stock_on_document_trigger ON documents", "006a drop trigger update_stock_on_document_trigger"),
        ("DROP TRIGGER IF EXISTS trg_update_stock_on_document ON documents", "006b drop trigger trg_update_stock_on_document"),
        ("DROP TRIGGER IF EXISTS update_stock ON documents", "006c drop trigger update_stock"),
        ("DROP FUNCTION IF EXISTS update_stock_on_document()", "006d drop function update_stock_on_document"),
    ]:
        try:
            with engine.connect() as conn:
                conn.execute(text(_sql))
                conn.commit()
            logger.info("Migration %s applied successfully", _label)
        except Exception as e:
            logger.warning("Migration %s skipped or failed (may be harmless): %s", _label, e)

    for _sql, _label in [
        (
            "DROP VIEW IF EXISTS v_stock_alerts",
            "008a drop v_stock_alerts",
        ),
        (
            "DROP TABLE IF EXISTS stock CASCADE",
            "008b drop stock",
        ),
        (
            """CREATE TABLE IF NOT EXISTS stock (
                id           SERIAL PRIMARY KEY,
                sort_id      INTEGER NOT NULL REFERENCES product_sorts(id),
                warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
                qty          NUMERIC(15,3) DEFAULT 0,
                updated_at   TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(sort_id, warehouse_id)
            )""",
            "008c create stock",
        ),
        (
            "ALTER TABLE document_items DROP COLUMN IF EXISTS product_id",
            "008d drop document_items.product_id",
        ),
        (
            "ALTER TABLE product_sorts DROP COLUMN IF EXISTS product_id",
            "008e drop product_sorts.product_id",
        ),
        (
            "DROP TABLE IF EXISTS products CASCADE",
            "008f drop products",
        ),
        (
            """CREATE OR REPLACE VIEW v_stock_alerts AS
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
            WHERE ps.is_active = true""",
            "008g v_stock_alerts",
        ),
        (
            """CREATE OR REPLACE VIEW v_counterparty_balances AS
            SELECT id, name, type, balance, is_active
            FROM counterparties
            WHERE is_active = true""",
            "008h v_counterparty_balances",
        ),
    ]:
        try:
            with engine.connect() as conn:
                conn.execute(text(_sql))
                conn.commit()
            logger.info("Migration %s applied successfully", _label)
        except Exception as e:
            logger.warning("Migration %s skipped or failed (may be harmless): %s", _label, e)

    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE OR REPLACE VIEW v_stock_alerts AS
                SELECT
                    s.id,
                    s.sort_id,
                    s.warehouse_id,
                    ps.name AS sort_name,
                    pc.name AS category_name,
                    w.name AS warehouse_name,
                    s.qty,
                    CASE
                        WHEN s.qty <= 0 THEN 'out_of_stock'
                        ELSE 'ok'
                    END AS alert_level,
                    s.updated_at
                FROM stock s
                JOIN product_sorts ps ON ps.id = s.sort_id
                JOIN product_categories pc ON pc.id = ps.category_id
                JOIN warehouses w ON w.id = s.warehouse_id
                WHERE ps.is_active = true
            """))
            conn.commit()
        logger.info("Migration 008a (v_stock_alerts) applied successfully")
    except Exception as e:
        logger.warning("Migration 008a skipped or failed (may be harmless): %s", e)

    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE OR REPLACE VIEW v_counterparty_balances AS
                SELECT
                    id,
                    name,
                    type,
                    balance,
                    is_active
                FROM counterparties
                WHERE is_active = true
            """))
            conn.commit()
        logger.info("Migration 009a (v_counterparty_balances) applied successfully")
    except Exception as e:
        logger.warning("Migration 009a skipped or failed (may be harmless): %s", e)

    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE OR REPLACE VIEW v_cashflow_monthly AS
                SELECT
                    DATE_TRUNC('month', txn_date) AS month,
                    SUM(CASE WHEN txn_type = 'income'  THEN amount ELSE 0 END) AS income,
                    SUM(CASE WHEN txn_type = 'expense' THEN amount ELSE 0 END) AS expense
                FROM transactions
                WHERE status = 'confirmed'
                GROUP BY 1
                ORDER BY 1 DESC
            """))
            conn.commit()
        logger.info("Migration 009b (v_cashflow_monthly) applied successfully")
    except Exception as e:
        logger.warning("Migration 009b skipped or failed (may be harmless): %s", e)

    for _sql, _label in [
        ("DROP VIEW IF EXISTS v_stock_alerts", "009a drop v_stock_alerts"),
        ("DROP TABLE IF EXISTS stock CASCADE", "009b drop stock"),
        ("""CREATE TABLE IF NOT EXISTS stock (
            id           SERIAL PRIMARY KEY,
            category_id  INTEGER NOT NULL REFERENCES product_categories(id),
            sort_id      INTEGER REFERENCES product_sorts(id),
            warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
            qty          NUMERIC(15,3) DEFAULT 0,
            updated_at   TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(category_id, sort_id, warehouse_id)
        )""", "009c create stock"),
        (
            "ALTER TABLE document_items ADD COLUMN IF NOT EXISTS category_id INTEGER REFERENCES product_categories(id)",
            "009d document_items.category_id",
        ),
        (
            """UPDATE document_items di
               SET category_id = ps.category_id
               FROM product_sorts ps
               WHERE ps.id = di.sort_id AND di.category_id IS NULL""",
            "009e backfill category_id",
        ),
        ("""CREATE OR REPLACE VIEW v_stock_alerts AS
            SELECT
                s.id, s.category_id, s.sort_id, s.warehouse_id,
                pc.name AS category_name,
                COALESCE(ps.name, '—') AS sort_name,
                w.name AS warehouse,
                s.qty, s.updated_at
            FROM stock s
            JOIN product_categories pc ON pc.id = s.category_id
            LEFT JOIN product_sorts ps  ON ps.id = s.sort_id
            JOIN warehouses w            ON w.id = s.warehouse_id
            WHERE pc.is_active = true""",
            "009f v_stock_alerts",
        ),
    ]:
        try:
            with engine.connect() as conn:
                conn.execute(text(_sql))
                conn.commit()
            logger.info("Migration %s applied successfully", _label)
        except Exception as e:
            logger.warning("Migration %s skipped or failed (may be harmless): %s", _label, e)