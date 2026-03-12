{{ config(materialized='view', tags=['staging']) }}
SELECT 
    ma_giao_dich AS transaction_id, ma_chi_nhanh AS branch_code, ten_chi_nhanh AS branch_name,
    ngay AS transaction_date, toYYYYMMDD(ngay) AS date_key, toYear(ngay) AS year, toMonth(ngay) AS month,
    toDayOfWeek(ngay) AS day_of_week, toQuarter(ngay) AS quarter,
    CASE WHEN toDayOfWeek(ngay) IN (6, 7) THEN 1 ELSE 0 END AS is_weekend
FROM {{ source('retail_source', 'raw_transactions') }}
