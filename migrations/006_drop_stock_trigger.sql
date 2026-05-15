-- Миграция 006: Удаление триггера update_stock_on_document
-- Причина: после миграции 005 product_id в document_items стал необязательным (nullable).
-- Триггер пытался вставить NULL в stock.product_id → NotNullViolation при проведении накладной.
-- Python-код recalculate_stock() уже корректно пересчитывает остатки с фильтром
-- WHERE di.product_id IS NOT NULL, поэтому триггер избыточен и конфликтует с ним.

DROP TRIGGER IF EXISTS update_stock_on_document_trigger ON documents;
DROP TRIGGER IF EXISTS trg_update_stock_on_document ON documents;
DROP TRIGGER IF EXISTS update_stock ON documents;

DROP FUNCTION IF EXISTS update_stock_on_document();
