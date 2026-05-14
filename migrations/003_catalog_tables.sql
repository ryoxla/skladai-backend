-- Миграция 003: Справочники товаров — сорта, страны, обновление категорий и единиц

-- 1. Добавить is_active к product_categories
ALTER TABLE product_categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- 2. Добавить is_active к units
ALTER TABLE units ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- 3. Создать таблицу сортов (привязаны к категории)
CREATE TABLE IF NOT EXISTS product_sorts (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    category_id INTEGER NOT NULL REFERENCES product_categories(id),
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Создать таблицу стран
CREATE TABLE IF NOT EXISTS countries (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100) NOT NULL UNIQUE,
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Добавить поля в document_items (единица измерения и страна — выбираются в накладной)
ALTER TABLE document_items ADD COLUMN IF NOT EXISTS unit_id    INTEGER REFERENCES units(id);
ALTER TABLE document_items ADD COLUMN IF NOT EXISTS country_id INTEGER REFERENCES countries(id);
