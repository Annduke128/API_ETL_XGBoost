{{
    config(
        materialized='table',
        engine='MergeTree()',
        partition_by='toYYYYMM(month)',
        order_by=['month', 'product_code', 'branch_code'],
        tags=['marts', 'sales', 'monthly']
    )
}}

SELECT
    toStartOfMonth(ngay) as month,
    toYYYYMM(ngay) as month_key,
    td.ma_hang as product_code,
    t.ma_chi_nhanh as branch_code,
    SUM(td.so_luong) as monthly_quantity,
    SUM(td.thanh_tien) as monthly_revenue,
    SUM(td.don_gia * td.so_luong * 0.7) as monthly_cost,
    SUM(td.thanh_tien - (td.don_gia * td.so_luong * 0.7)) as monthly_profit,
    0.3 as avg_profit_margin,
    COUNT(DISTINCT ngay) as active_days,
    now() as etl_timestamp
FROM {{ source('retail_source', 'raw_transaction_details') }} td
JOIN {{ source('retail_source', 'raw_transactions') }} t ON td.transaction_id = t.id
GROUP BY toStartOfMonth(ngay), toYYYYMM(ngay), td.ma_hang, t.ma_chi_nhanh
