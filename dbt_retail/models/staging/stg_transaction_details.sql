{{
    config(
        materialized='view'
    )
}}

WITH source AS (
    SELECT * FROM {{ source('retail_source', 'staging_transaction_details') }}
),

renamed AS (
    SELECT
        id AS detail_id,
        giao_dich_id AS transaction_id,
        product_id,
        ma_hang AS product_code,
        so_luong AS quantity,
        gia_ban AS unit_price,
        gia_ban AS selling_price,
        gia_von AS cost_price,
        (gia_ban * so_luong) AS line_revenue,
        (gia_von * so_luong) AS line_cost,
        loi_nhuan AS line_profit,
        tong_loi_nhuan AS total_line_profit,
        created_at
    FROM source
)

SELECT * FROM renamed
