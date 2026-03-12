{{ config(materialized='view') }}
SELECT 
    ma_hang AS product_id,
    ma_hang AS product_code,
    ten_hang AS product_name,
    '' AS barcode,
    '' AS brand,
    don_vi_tinh AS unit_of_measure,
    cap_1 AS category_level_1,
    cap_2 AS category_level_2,
    cap_3 AS category_level_3,
    toFloat64(0) AS default_selling_price,
    toFloat64(0) AS default_cost_price,
    toFloat64(0) AS default_margin_rate,
    created_at,
    created_at AS updated_at
FROM {{ source('retail_source', 'raw_products') }}
