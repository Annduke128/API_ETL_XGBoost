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
        chi_nhanh_id AS branch_id,
        thoi_gian AS transaction_timestamp,
        tong_tien_hang AS gross_amount,
        giam_gia AS discount_amount,
        doanh_thu AS revenue,
        tong_gia_von AS total_cost,
        loi_nhuan_gop AS gross_profit,
        created_at
    FROM source
)

SELECT * FROM renamed
