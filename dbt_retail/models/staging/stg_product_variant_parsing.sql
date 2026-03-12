{{ config(materialized='view') }}
SELECT 
    product_id,
    product_code,
    product_name AS clean_name,
    '' AS packaging_type,
    '' AS weight,
    '' AS unit,
    0 AS weight_normalized_g_or_ml,
    category_level_1 AS product_family,
    default_selling_price,
    default_cost_price
FROM {{ ref('stg_products') }}
