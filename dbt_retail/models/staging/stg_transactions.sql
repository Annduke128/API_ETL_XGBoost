{{
    config(
        materialized='view'
    )
}}

WITH source AS (
    SELECT * FROM {{ source('retail_source', 'staging_transactions') }}
),

renamed AS (
    SELECT
        id AS transaction_id,
        ma_giao_dich AS transaction_code,
        -- chi_nhanh_id không có, dùng ma_chi_nhanh
        ma_chi_nhanh AS branch_id,
        ma_chi_nhanh AS branch_code,
        ten_chi_nhanh AS branch_name,
        -- ngay là String (YYYY-MM-DD), parse sang Date
        toDate(ngay) AS transaction_date,
        toDateTime(ngay) AS transaction_timestamp,
        -- Các cột tài chính không có trong staging, để 0
        toFloat64(0) AS gross_amount,
        toFloat64(0) AS discount_amount,
        toFloat64(0) AS revenue,
        toFloat64(0) AS total_cost,
        toFloat64(0) AS gross_profit,
        -- created_at không có, dùng now()
        now() AS created_at
    FROM source
)

SELECT * FROM renamed
