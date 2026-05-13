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