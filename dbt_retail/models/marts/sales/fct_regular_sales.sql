{{
  config(
    materialized = 'table',
    engine = 'MergeTree()',
    order_by = ['transaction_date', 'product_code', 'branch_code'],
    partition_by = "toYYYYMM(transaction_date)",
    tags = ['marts', 'sales', 'ml', 'baseline']
  )
}}

-- Model này chứa doanh số THƯỜNG (không khuyến mại)
-- Dùng để train ML model cho baseline demand prediction
-- Loại bỏ các sản phẩm category 'Khuyến mại%' để tránh làm méo pattern

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
    
    -- Flag cho ML
    0 AS is_promotional_sale,
    'regular' AS sale_type

FROM {{ ref('fct_daily_sales') }} f
WHERE f.product_code NOT IN (
    SELECT product_code 
    FROM {{ ref('dim_product') }} 
    WHERE lower(category_level_1) LIKE '%khuyến mại%' 
       OR lower(category_level_1) LIKE '%khuyen mai%'
)
