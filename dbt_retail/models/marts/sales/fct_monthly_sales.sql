{{
    config(
        materialized='table',
        engine='MergeTree()',
        partition_by='toYYYYMM(month)',
        order_by=['month', 'product_code', 'branch_code'],
        tags=['marts', 'sales', 'monthly']
    )
}}
-- fct_monthly_sales: Monthly aggregated sales
-- Source: staging tables từ PostgreSQL sync
SELECT
    toStartOfMonth(toDate(t.ngay)) as month,
    toYYYYMM(toDate(t.ngay)) as month_key,
    td.ma_hang as product_code,
    t.ma_chi_nhanh as branch_code,
    SUM(td.so_luong) as monthly_quantity,
    SUM(td.thanh_tien) as monthly_revenue,
    SUM(td.so_luong * COALESCE(p.gia_von_mac_dinh, td.don_gia * 0.7)) as monthly_cost,
    SUM(td.thanh_tien - (td.so_luong * COALESCE(p.gia_von_mac_dinh, td.don_gia * 0.7))) as monthly_profit,
    CASE 
        WHEN SUM(td.thanh_tien) > 0 
        THEN (SUM(td.thanh_tien) - SUM(td.so_luong * COALESCE(p.gia_von_mac_dinh, td.don_gia * 0.7))) / SUM(td.thanh_tien)
        ELSE 0.3 
    END as avg_profit_margin,
    COUNT(DISTINCT toDate(t.ngay)) as active_days,
    now() as etl_timestamp
FROM {{ source('retail_source', 'staging_transaction_details') }} td
JOIN {{ source('retail_source', 'staging_transactions') }} t 
    ON td.transaction_id = t.id
LEFT JOIN {{ source('retail_source', 'staging_products') }} p 
    ON td.ma_hang = p.ma_hang
GROUP BY 
    toStartOfMonth(toDate(t.ngay)), 
    toYYYYMM(toDate(t.ngay)), 
    td.ma_hang, 
    t.ma_chi_nhanh
