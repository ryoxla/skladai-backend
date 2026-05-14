-- Миграция 004: Переименование "Категория" → "Товар" в справочнике
-- Логическое переименование: product_categories теперь называется "Товары",
-- product_sorts — "Сорта", привязанные к товару.
-- Структура таблиц не меняется, обновляются только комментарии в БД.

COMMENT ON TABLE product_categories IS 'Справочник товаров (ранее: категории товаров)';
COMMENT ON TABLE product_sorts IS 'Справочник сортов товаров';
COMMENT ON COLUMN product_sorts.category_id IS 'ID товара (product_categories.id)';
