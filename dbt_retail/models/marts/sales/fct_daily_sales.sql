{{ config(
    materialized='table',
    engine='MergeTree()',
    partition_by='toYYYYMMDD(transaction_date)',
    order_by=['transaction_date', 'product_code', 'branch_code'],
    tags=['marts', 'sales', 'ml_source']
) }}

SELECT
    t.ngay AS transaction_date,
    toYYYYMMDD(t.ngay) AS date_key,
    d.ma_hang AS product_code,
    p.ma_hang AS product_id,
    t.ma_chi_nhanh AS branch_code,
    b.ma_chi_nhanh AS branch_id,
    count() AS transaction_count,
    sum(d.so_luong) AS quantity_sold,
    sum(d.thanh_tien) AS gross_revenue,
    sum(d.so_luong * 0) AS cost_of_goods_sold,  -- Placeholder
    sum(d.thanh_tien) AS gross_profit,  -- Placeholder
    avg(d.don_gia) AS avg_selling_price,
    0 AS profit_margin,  -- Placeholder
    now() AS etl_timestamp
FROM {{ source('retail_source', 'raw_transaction_details') }} d
JOIN {{ source('retail_source', 'raw_transactions') }} t ON d.transaction_id = t.id
LEFT JOIN {{ source('retail_source', 'raw_products') }} p ON d.ma_hang = p.ma_hang
LEFT JOIN {{ source('retail_source', 'raw_branches') }} b ON t.ma_chi_nhanh = b.ma_chi_nhanh
GROUP BY t.ngay, d.ma_hang, p.ma_hang, t.ma_chi_nhanh, b.ma_chi_nhanh
