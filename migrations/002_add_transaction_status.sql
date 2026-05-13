-- Миграция 002: Добавление статуса в таблицу транзакций
-- Описание: финансовые документы (приходы/расходы) получают статус
--   draft     = не проведён (не влияет на балансы)
--   confirmed = проведён (влияет на балансы)

-- Шаг 1: Добавить колонку status, существующие записи → 'confirmed'
ALTER TABLE transactions
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'confirmed';

-- Шаг 2: Сменить дефолт на 'draft' для новых записей
ALTER TABLE transactions
    ALTER COLUMN status SET DEFAULT 'draft';

-- Проверка
SELECT
    status,
    COUNT(*) AS cnt
FROM transactions
GROUP BY status;
