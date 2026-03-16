{{
    config(
        materialized='view'
    )
}}

SELECT
    t.ngay AS transaction_date,
    td.ma_hang AS product_code,
    COALESCE(td.ten_hang, '') AS product_name,
    '' AS brand,
    '' AS category_l1,
    '' AS category_l2,
    SUM(td.so_luong) AS units_sold,
    SUM(td.thanh_tien) AS revenue,
    SUM(td.don_gia * td.so_luong * 0.7) AS cogs,
    SUM(td.thanh_tien - (td.don_gia * td.so_luong * 0.7)) AS profit,
    COUNT(DISTINCT td.transaction_id) AS transaction_count
FROM {{ source('retail_source', 'raw_transaction_details') }} td
JOIN {{ source('retail_source', 'raw_transactions') }} t ON td.transaction_id = t.id
GROUP BY t.ngay, td.ma_hang, td.ten_hang
