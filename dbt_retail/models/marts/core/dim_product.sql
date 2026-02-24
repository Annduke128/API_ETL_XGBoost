{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['product_id']
    )
}}

WITH products AS (
    SELECT * FROM {{ ref('stg_products') }}
),

product_parsed AS (
    SELECT 
        product_code,
        clean_name,
        packaging_type,
        weight,
        unit,
        weight_normalized_g_or_ml
    FROM {{ ref('stg_product_variant_parsing') }}
),

product_performance AS (
    SELECT * FROM {{ ref('int_product_performance') }}
),

dim_product AS (
    SELECT
        p.product_id,
        p.product_code,
        p.barcode,
        p.product_name,                         -- Raw name
        pp.clean_name,                          -- Parsed name (no weight, no packaging)
        p.brand,
        p.category_level_1,
        p.category_level_2,
        p.category_level_3,
        
        -- Parsed fields từ product_name
        pp.packaging_type,
        pp.weight,
        pp.unit,
        pp.weight_normalized_g_or_ml,
        
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
        COALESCE(pp_perf.abc_class, 'N/A') AS abc_class,
        
        -- Hiệu suất
        COALESCE(pp_perf.total_revenue, 0) AS total_historical_revenue,
        COALESCE(pp_perf.total_quantity_sold, 0) AS total_historical_quantity,
        COALESCE(pp_perf.profit_margin, 0) AS historical_profit_margin,
        
        -- Trạng thái (ClickHouse syntax)
        CASE 
            WHEN pp_perf.last_sale_date IS NULL THEN 'New'
            WHEN pp_perf.last_sale_date >= today() - 30 THEN 'Active'
            WHEN pp_perf.last_sale_date >= today() - 90 THEN 'Slow Moving'
            ELSE 'Inactive'
        END AS product_status,
        
        p.created_at,
        p.updated_at
        
    FROM products p
    LEFT JOIN product_parsed pp ON p.product_code = pp.product_code
    LEFT JOIN product_performance pp_perf ON p.product_code = pp_perf.product_code
)

SELECT * FROM dim_product
