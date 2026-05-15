-- Удалить старый view и stock
DROP VIEW IF EXISTS v_stock_alerts;
DROP TABLE IF EXISTS stock CASCADE;

-- Новая stock по sort_id
CREATE TABLE stock (
  id           SERIAL PRIMARY KEY,
  sort_id      INTEGER NOT NULL REFERENCES product_sorts(id),
  warehouse_id INTEGER NOT NULL REFERENCES warehouses(id),
  qty          NUMERIC(15,3) DEFAULT 0,
  updated_at   TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(sort_id, warehouse_id)
);

-- Почистить старые FK
ALTER TABLE document_items DROP COLUMN IF EXISTS product_id;
ALTER TABLE product_sorts  DROP COLUMN IF EXISTS product_id;

-- Удалить products
DROP TABLE IF EXISTS products CASCADE;

-- Новый view
CREATE OR REPLACE VIEW v_stock_alerts AS
SELECT
  s.id, s.sort_id, s.warehouse_id,
  pc.name  AS category_name,
  ps.name  AS sort_name,
  w.name   AS warehouse,
  s.qty,
  s.updated_at
FROM stock s
JOIN product_sorts ps      ON ps.id = s.sort_id
JOIN product_categories pc ON pc.id = ps.category_id
JOIN warehouses w           ON w.id = s.warehouse_id
WHERE ps.is_active = true;
