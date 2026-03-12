{{ config(materialized='view') }}
SELECT 
    toString(id) AS transaction_id,
    ma_giao_dich AS transaction_code,
    ma_chi_nhanh AS branch_id,
    ma_chi_nhanh AS branch_code,
    ten_chi_nhanh AS branch_name,
    ngay AS transaction_date,
    toDateTime(ngay) AS transaction_timestamp,
    toFloat64(0) AS revenue,
    toFloat64(0) AS gross_profit,
    toFloat64(0) AS total_amount,
    'cash' AS payment_method,
    id AS id_num
FROM {{ source('retail_source', 'raw_transactions') }}
