{{
  config(
    materialized = 'view',
    tags = ['marts', 'products', 'abc', 'daily']
  )
}}

WITH product_revenue AS (
    SELECT 
        p.ma_hang AS product_code,
        p.ten_hang AS product_name,
        p.cap_1 AS category_level_1,
        p.cap_2 AS category_level_2,
        p.cap_3 AS category_level_3,
        COALESCE(SUM(td.thanh_tien), 0) AS total_revenue,
        COALESCE(SUM(td.so_luong), 0) AS total_quantity,
        COUNT(DISTINCT t.ngay) AS active_days
    FROM {{ source('retail_source', 'raw_products') }} p
    LEFT JOIN {{ source('retail_source', 'raw_transaction_details') }} td ON p.ma_hang = td.ma_hang
    LEFT JOIN {{ source('retail_source', 'raw_transactions') }} t ON td.transaction_id = t.id
    GROUP BY p.ma_hang, p.ten_hang, p.cap_1, p.cap_2, p.cap_3
),

total_revenue AS (
    SELECT SUM(total_revenue) AS grand_total FROM product_revenue
),

ranked_products AS (
    SELECT 
        *,
        SUM(total_revenue) OVER (ORDER BY total_revenue DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_revenue,
        (SELECT grand_total FROM total_revenue) AS grand_total
    FROM product_revenue
),

abc_classified AS (
    SELECT 
        product_code, product_name,
        category_level_1, category_level_2, category_level_3,
        total_revenue, total_quantity, active_days,
        cumulative_revenue,
        cumulative_revenue / grand_total * 100 AS cumulative_pct,
        CASE 
            WHEN cumulative_revenue / grand_total * 100 <= 80 THEN 'A'
            WHEN cumulative_revenue / grand_total * 100 <= 95 THEN 'B'
            ELSE 'C'
        END AS abc_class,
        NTILE(100) OVER (ORDER BY total_revenue DESC) AS revenue_percentile
    FROM ranked_products
)

SELECT 
    product_code, product_name,
    category_level_1, category_level_2, category_level_3,
    total_revenue AS total_historical_revenue,
    total_quantity AS total_historical_quantity,
    active_days, abc_class, revenue_percentile,
    now() AS calculated_at
FROM abc_classified
ORDER BY total_revenue DESC
