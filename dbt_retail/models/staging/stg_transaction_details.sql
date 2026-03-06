{{
    config(
        materialized='view'
    )
}}

WITH source AS (
    SELECT 
        id,
        giao_dich_id,
        product_id,
        toInt32OrNull(so_luong) as so_luong,
        toFloat64OrNull(gia_ban) as gia_ban,
        toFloat64OrNull(gia_von) as gia_von,
        toFloat64OrNull(loi_nhuan) as loi_nhuan,
        toFloat64OrNull(tong_loi_nhuan) as tong_loi_nhuan,
        created_at
    FROM {{ source('retail_source', 'staging_transaction_details') }}
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
        s.so_luong AS quantity,
        s.gia_ban AS unit_price,
        s.gia_ban AS selling_price,
        s.gia_von AS cost_price,
        (s.gia_ban * s.so_luong) AS line_revenue,
        (s.gia_von * s.so_luong) AS line_cost,
        s.loi_nhuan AS line_profit,
        s.tong_loi_nhuan AS total_line_profit,
        s.created_at
    FROM source s
    LEFT JOIN products_ref p ON s.product_id = p.product_id
)

SELECT * FROM renamed
