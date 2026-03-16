{{
    config(
        materialized='view'
    )
}}

-- Staging model cho transaction details
-- Source: staging_transaction_details trong ClickHouse

WITH source AS (
    SELECT * FROM {{ source('retail_source', 'staging_transaction_details') }}
),

products_ref AS (
    SELECT 
        product_id,
        product_code,
        product_name,
        brand,
        category_level_1 AS category_l1,
        category_level_2 AS category_l2
    FROM {{ ref('stg_products') }}
),

transactions_ref AS (
    SELECT
        toInt64(transaction_id) AS transaction_id_int,
        branch_code,
        transaction_date
    FROM {{ ref('stg_transactions') }}
),

renamed AS (
    SELECT
        toString(s.id) AS detail_id,
        toString(s.transaction_id) AS transaction_id,
        s.ma_hang AS product_code,
        s.ten_hang AS product_name,
        COALESCE(p.brand, '') AS brand,
        COALESCE(p.category_l1, '') AS category_l1,
        COALESCE(p.category_l2, '') AS category_l2,
        s.so_luong AS quantity,
        s.don_gia AS unit_price,
        s.don_gia AS selling_price,
        s.chiet_khau AS discount_amount,
        s.thue_gtgt AS tax_amount,
        s.thanh_tien AS line_total,
        -- Tính line_revenue = so_luong * don_gia
        s.so_luong * s.don_gia AS line_revenue,
        -- line_cost không có trong source, để 0
        toFloat64(0) AS line_cost,
        toFloat64(0) AS line_profit,
        toFloat64(0) AS cost_price,
        t.branch_code,
        t.transaction_date
    FROM source s
    LEFT JOIN products_ref p ON s.ma_hang = p.product_code
    LEFT JOIN transactions_ref t ON s.transaction_id = t.transaction_id_int
)

SELECT * FROM renamed
