{{
  config(
    materialized = 'view',
    tags = ['marts', 'products', 'abc', 'daily']
  )
}}

/*
    ABC Classification cho sản phẩm
    
    Phân loại:
    - A: Top ~20% sản phẩm, ~80% tổng doanh thu
    - B: ~30% sản phẩm, ~15% tổng doanh thu  
    - C: ~50% sản phẩm, ~5% tổng doanh thu
    
    Logic:
    1. Tính tổng doanh thu lịch sử theo sản phẩm
    2. Sắp xếp giảm dần theo doanh thu
    3. Tính cumulative percentage
    4. Gán ABC dựa trên cumulative percentage
*/

WITH product_revenue AS (
    -- Tính tổng doanh thu theo sản phẩm từ fct_daily_sales
    SELECT 
        p.product_id,
        p.product_code,
        p.product_name,
        p.category_level_1,
        p.category_level_2,
        p.category_level_3,
        COALESCE(SUM(f.daily_revenue), 0) as total_revenue,
        COALESCE(SUM(f.daily_quantity), 0) as total_quantity,
        COUNT(DISTINCT f.transaction_date) as active_days
    FROM {{ source('retail_source', 'staging_products') }} p
    LEFT JOIN {{ ref('fct_daily_sales') }} f 
        ON p.product_code = f.product_code
    GROUP BY 
        p.product_id,
        p.product_code,
        p.product_name,
        p.category_level_1,
        p.category_level_2,
        p.category_level_3
),

total_revenue AS (
    -- Tính tổng doanh thu toàn hệ thống
    SELECT SUM(total_revenue) as grand_total
    FROM product_revenue
),

ranked_products AS (
    -- Sắp xếp và tính cumulative
    SELECT 
        *,
        SUM(total_revenue) OVER (ORDER BY total_revenue DESC 
                                 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as cumulative_revenue,
        grand_total
    FROM product_revenue
    CROSS JOIN total_revenue
),

abc_classified AS (
    -- Gán ABC classification
    SELECT 
        product_id,
        product_code,
        product_name,
        category_level_1,
        category_level_2,
        category_level_3,
        total_revenue,
        total_quantity,
        active_days,
        cumulative_revenue,
        cumulative_revenue / grand_total * 100 as cumulative_pct,
        -- ABC classification logic
        CASE 
            WHEN cumulative_revenue / grand_total * 100 <= 80 THEN 'A'
            WHEN cumulative_revenue / grand_total * 100 <= 95 THEN 'B'
            ELSE 'C'
        END as abc_class,
        -- Thêm thông tin phân vị để debug
        NTILE(100) OVER (ORDER BY total_revenue DESC) as revenue_percentile
    FROM ranked_products
)

SELECT 
    product_id,
    product_code,
    product_name,
    category_level_1,
    category_level_2,
    category_level_3,
    total_revenue as total_historical_revenue,
    total_quantity as total_historical_quantity,
    active_days,
    abc_class,
    revenue_percentile,
    now() as calculated_at
FROM abc_classified
ORDER BY total_revenue DESC
