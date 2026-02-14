{{
    config(
        materialized='table',
        unique_key='product_id'
    )
}}

WITH products AS (
    SELECT * FROM {{ ref('stg_products') }}
),

product_performance AS (
    SELECT * FROM {{ ref('int_product_performance') }}
),

dim_product AS (
    SELECT
        p.product_id,
        p.product_code,
        p.barcode,
        p.product_name,
        p.brand,
        p.category_level_1,
        p.category_level_2,
        p.category_level_3,
        
        -- Giá
        p.default_cost_price,
        p.default_selling_price,
        p.default_margin_rate,
        
        -- Phân loại giá
        CASE 
            WHEN p.default_selling_price >= 1000000 THEN 'Premium'
            WHEN p.default_selling_price >= 500000 THEN 'Mid-range'
            WHEN p.default_selling_price >= 200000 THEN 'Economy'
            ELSE 'Budget'
        END AS price_tier,
        
        -- Phân loại ABC
        COALESCE(pp.abc_class, 'N/A') AS abc_class,
        
        -- Hiệu suất
        COALESCE(pp.total_historical_revenue, 0) AS total_historical_revenue,
        COALESCE(pp.total_historical_quantity, 0) AS total_historical_quantity,
        COALESCE(pp.historical_profit_margin, 0) AS historical_profit_margin,
        
        -- Trạng thái
        CASE 
            WHEN pp.last_sale_date IS NULL THEN 'New'
            WHEN pp.last_sale_date >= CURRENT_DATE - INTERVAL '30 days' THEN 'Active'
            WHEN pp.last_sale_date >= CURRENT_DATE - INTERVAL '90 days' THEN 'Slow Moving'
            ELSE 'Inactive'
        END AS product_status,
        
        p.created_at,
        p.updated_at
        
    FROM products p
    LEFT JOIN product_performance pp ON p.product_code = pp.product_code
)

SELECT * FROM dim_product
