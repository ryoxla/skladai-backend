RECALC_SQL = """
    INSERT INTO stock (sort_id, warehouse_id, qty)
    SELECT
        di.sort_id,
        d.warehouse_id,
        SUM(di.qty * CASE d.doc_type
            WHEN 'receipt'    THEN  1
            WHEN 'shipment'   THEN -1
            WHEN 'return_in'  THEN  1
            WHEN 'return_out' THEN -1
            WHEN 'writeoff'   THEN -1
            ELSE 0
        END)
    FROM document_items di
    JOIN documents d ON d.id = di.document_id
    WHERE d.status = 'confirmed'
      AND d.warehouse_id IS NOT NULL
      AND di.sort_id IS NOT NULL
    GROUP BY di.sort_id, d.warehouse_id
    ON CONFLICT (sort_id, warehouse_id)
    DO UPDATE SET qty = EXCLUDED.qty, updated_at = NOW()
"""
