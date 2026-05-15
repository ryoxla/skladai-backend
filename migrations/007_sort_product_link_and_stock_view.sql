-- Миграция 007: Привязка сортов к товарам и создание view v_stock_alerts
--
-- Проблема: позиции накладных с sort_id (без product_id) игнорировались при
-- пересчёте остатков (RECALC_SQL фильтровал WHERE di.product_id IS NOT NULL),
-- поэтому товары из проведённых накладных не попадали в остатки.
--
-- Исправление:
-- 1. Добавляем product_id в product_sorts — каждый сорт привязывается к товару.
-- 2. Создаём/обновляем view v_stock_alerts для страницы остатков.

-- 1. Связь сорт → товар
ALTER TABLE product_sorts ADD COLUMN IF NOT EXISTS product_id INTEGER REFERENCES products(id);

-- 2. View для страницы остатков (используется в GET /api/stock/)
CREATE OR REPLACE VIEW v_stock_alerts AS
SELECT
    s.id,
    s.product_id,
    s.warehouse_id,
    p.name,
    p.sku,
    p.min_qty,
    u.short_name AS unit_name,
    w.name       AS warehouse_name,
    s.qty,
    CASE
        WHEN s.qty = 0          THEN 'out_of_stock'
        WHEN s.qty <= p.min_qty THEN 'low_stock'
        ELSE 'ok'
    END AS alert_level,
    s.updated_at
FROM stock s
JOIN products p ON p.id = s.product_id
JOIN warehouses w ON w.id = s.warehouse_id
LEFT JOIN units u ON u.id = p.unit_id
WHERE p.is_active = true;
