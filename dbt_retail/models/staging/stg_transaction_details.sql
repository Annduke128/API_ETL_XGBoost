{{
    config(
        materialized='view'
    )
}}

WITH source AS (
    SELECT * FROM {{ source('retail_source', 'staging_transaction_details') }}
),

products_ref AS (
    SELECT 
        id AS product_id,
        ma_hang AS product_code,
        ten_hang AS product_name,
        thuong_hieu AS brand,
        nhom_hang_cap_1 AS category_l1,
        nhom_hang_cap_2 AS category_l2
    FROM {{ source('retail_source', 'staging_products') }}
),

renamed AS (
    SELECT
        s.id AS detail_id,
        s.giao_dich_id AS transaction_id,
        s.product_id,
        p.product_code,
        p.product_name,
        p.brand,
        p.category_l1,
        p.category_l2,
        toInt32(s.so_luong) AS quantity,
        toFloat64(s.gia_ban) AS unit_price,
        toFloat64(s.gia_ban) AS selling_price,
        toFloat64(s.gia_von) AS cost_price,
        (toFloat64(s.gia_ban) * toInt32(s.so_luong)) AS line_revenue,
        (toFloat64(s.gia_von) * toInt32(s.so_luong)) AS line_cost,
        toFloat64(s.loi_nhuan) AS line_profit,
        s.tong_loi_nhuan AS total_line_profit,
        s.created_at
    FROM source s
    LEFT JOIN products_ref p ON s.product_id = p.product_id
)

SELECT * FROM renamed
