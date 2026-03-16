{{
    config(
        materialized='view'
    )
}}
-- int_inventory_movement: Daily inventory movement summary
-- Source: staging tables từ PostgreSQL sync
SELECT
    toDate(t.ngay) AS transaction_date,
    td.ma_hang AS product_code,
    COALESCE(td.ten_hang, '') AS product_name,
    '' AS brand,
    '' AS category_l1,
    '' AS category_l2,
    SUM(td.so_luong) AS units_sold,
    SUM(td.thanh_tien) AS revenue,
    SUM(td.so_luong * COALESCE(p.gia_von_mac_dinh, td.don_gia * 0.7)) AS cogs,
    SUM(td.thanh_tien - (td.so_luong * COALESCE(p.gia_von_mac_dinh, td.don_gia * 0.7))) AS profit,
    COUNT(DISTINCT td.transaction_id) AS transaction_count
FROM {{ source('retail_source', 'staging_transaction_details') }} td
JOIN {{ source('retail_source', 'staging_transactions') }} t 
    ON td.transaction_id = t.id
LEFT JOIN {{ source('retail_source', 'staging_products') }} p 
    ON td.ma_hang = p.ma_hang
GROUP BY toDate(t.ngay), td.ma_hang, td.ten_hang
