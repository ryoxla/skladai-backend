-- Миграция 005: document_items — sort_id, product_id становится необязательным
-- Позиции накладной теперь работают с категорией+сортом (без прямой привязки к product_id)

-- 1. Сделать product_id необязательным
ALTER TABLE document_items ALTER COLUMN product_id DROP NOT NULL;

-- 2. Добавить sort_id для выбора сорта в накладной
ALTER TABLE document_items ADD COLUMN IF NOT EXISTS sort_id INTEGER REFERENCES product_sorts(id);
