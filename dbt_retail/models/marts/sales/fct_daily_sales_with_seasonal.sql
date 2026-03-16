{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['transaction_date', 'branch_code', 'product_code'],
        partition_by=['toYear(transaction_date)'],
        tags=['marts', 'sales', 'ml_features']
    )
}}

WITH daily_sales AS (
    SELECT
        t.ngay AS transaction_date,
        td.ma_hang AS product_code,
        t.ma_chi_nhanh AS branch_code,
        SUM(td.so_luong) AS quantity_sold,
        SUM(td.thanh_tien) AS gross_revenue
    FROM {{ source('retail_source', 'raw_transaction_details') }} td
    JOIN {{ source('retail_source', 'raw_transactions') }} t ON td.transaction_id = t.id
    GROUP BY t.ngay, td.ma_hang, t.ma_chi_nhanh
)

SELECT 
    d.*,
    CASE 
        WHEN toMonth(d.transaction_date) = 1 THEN 'Winter'
        WHEN toMonth(d.transaction_date) IN (2,3) THEN 'Spring'
        WHEN toMonth(d.transaction_date) IN (4,5,6) THEN 'Summer'
        WHEN toMonth(d.transaction_date) IN (7,8,9) THEN 'Autumn'
        ELSE 'Winter'
    END AS season,
    CASE 
        WHEN toDayOfWeek(d.transaction_date) IN (6,7) THEN 1.2
        ELSE 1.0
    END AS seasonal_factor,
    0 AS is_peak_day
FROM daily_sales d
