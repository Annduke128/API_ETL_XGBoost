{{
  config(
    materialized = 'table',
    engine = 'MergeTree()',
    order_by = ['transaction_date', 'product_code', 'branch_code'],
    partition_by = "toYYYYMM(transaction_date)",
    tags = ['marts', sales', 'ml', 'promotion']
  )
}}

-- Model này chứa doanh số KHUYẾN MẠI
-- Dùng để train ML model riêng cho promotion demand prediction
-- Các sản phẩm này có pattern khác biệt so với baseline

WITH promotion_products AS (
    SELECT 
        product_code,
        category_level_1 AS promotion_category,
        category_level_2 AS promotion_subcategory
    FROM {{ ref('dim_product') }}
    WHERE lower(category_level_1) LIKE '%khuyến mại%' 
       OR lower(category_level_1) LIKE '%khuyen mai%'
)

SELECT 
    f.transaction_date,
    f.date_key,
    f.product_code,
    f.product_id,
    f.branch_code,
    f.branch_id,
    f.transaction_count,
    f.quantity_sold,
    f.gross_revenue,
    f.cost_of_goods_sold,
    f.gross_profit,
    f.avg_selling_price,
    f.avg_profit_per_unit,
    f.profit_margin,
    f.etl_timestamp,
    
    -- Promotion metadata
    p.promotion_category,
    p.promotion_subcategory,
    
    -- Flag cho ML
    1 AS is_promotional_sale,
    'promotional' AS sale_type

FROM {{ ref('fct_daily_sales') }} f
INNER JOIN promotion_products p ON f.product_code = p.product_code
