{{ config(materialized='view', tags=['staging']) }}
SELECT 
    ma_giao_dich AS transaction_id, ma_chi_nhanh AS branch_code, ten_chi_nhanh AS branch_name,
    toDate(ngay) AS transaction_date, toYYYYMMDD(toDate(ngay)) AS date_key, toYear(toDate(ngay)) AS year, toMonth(toDate(ngay)) AS month,
    toDayOfWeek(toDate(ngay)) AS day_of_week, toQuarter(toDate(ngay)) AS quarter,
    CASE WHEN toDayOfWeek(toDate(ngay)) IN (6, 7) THEN 1 ELSE 0 END AS is_weekend
FROM {{ source('retail_source', 'staging_transactions') }}
