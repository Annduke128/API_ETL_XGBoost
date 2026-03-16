{{ config(
    materialized='table',
    engine='MergeTree()',
    partition_by='toYYYYMM(transaction_date)',
    order_by=['transaction_date', 'product_code', 'branch_code'],
    tags=['marts', 'sales', 'ml_source']
) }}
-- fct_daily_sales: Daily sales fact table
-- Source: staging tables từ PostgreSQL (đã sync qua sync-data job)
SELECT
    -- staging_transactions.ngay là String (YYYY-MM-DD), cần parse sang Date
    toDate(t.ngay) AS transaction_date,
    toYYYYMMDD(toDate(t.ngay)) AS date_key,
    td.ma_hang AS product_code,
    p.ma_hang AS product_id,
    t.ma_chi_nhanh AS branch_code,
    b.ma_chi_nhanh AS branch_id,
    count() AS transaction_count,
    sum(td.so_luong) AS quantity_sold,
    sum(td.thanh_tien) AS gross_revenue,
    -- Cost sẽ được tính từ giá vốn trong products nếu có
    sum(td.so_luong * COALESCE(p.gia_von_mac_dinh, 0)) AS cost_of_goods_sold,
    sum(td.thanh_tien) AS gross_profit,
    avg(td.don_gia) AS avg_selling_price,
    -- Profit margin = (revenue - cost) / revenue
    CASE 
        WHEN sum(td.thanh_tien) > 0 
        THEN (sum(td.thanh_tien) - sum(td.so_luong * COALESCE(p.gia_von_mac_dinh, 0))) / sum(td.thanh_tien)
        ELSE 0 
    END AS profit_margin,
    now() AS etl_timestamp
FROM {{ source('retail_source', 'staging_transactions') }} t
JOIN {{ source('retail_source', 'staging_transaction_details') }} td 
    ON td.transaction_id = t.id
LEFT JOIN {{ source('retail_source', 'staging_products') }} p 
    ON td.ma_hang = p.ma_hang
LEFT JOIN {{ source('retail_source', 'staging_branches') }} b 
    ON t.ma_chi_nhanh = b.ma_chi_nhanh
GROUP BY 
    toDate(t.ngay), 
    td.ma_hang, 
    p.ma_hang, 
    t.ma_chi_nhanh, 
    b.ma_chi_nhanh
