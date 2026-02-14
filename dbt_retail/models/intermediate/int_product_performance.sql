{{
    config(
        materialized='ephemeral'
    )
}}

WITH transaction_details AS (
    SELECT * FROM {{ ref('stg_transaction_details') }}
),

product_metrics AS (
    SELECT
        product_code,
        product_name,
        brand,
        category_l1,
        category_l2,
        category_l3,
        
        -- Tổng số liệu
        COUNT(DISTINCT transaction_id) AS total_transactions,
        SUM(quantity) AS total_quantity_sold,
        SUM(line_revenue) AS total_revenue,
        SUM(line_profit) AS total_profit,
        
        -- Giá trị trung bình
        AVG(selling_price) AS avg_selling_price,
        AVG(profit) AS avg_profit_per_unit,
        
        -- Biên lợi nhuận
        CASE 
            WHEN SUM(line_revenue) > 0 
            THEN SUM(line_profit) / SUM(line_revenue) 
            ELSE 0 
        END AS profit_margin,
        
        -- Ngày gần nhất
        MAX(transaction_date) AS last_sale_date,
        MIN(transaction_date) AS first_sale_date,
        
        -- Số ngày bán hàng
        COUNT(DISTINCT transaction_date) AS selling_days
        
    FROM transaction_details
    GROUP BY 1, 2, 3, 4, 5, 6
),

abc_classification AS (
    SELECT
        *,
        SUM(total_revenue) OVER (ORDER BY total_revenue DESC) 
            / SUM(total_revenue) OVER () AS revenue_cum_pct,
        
        -- Phân loại ABC
        CASE 
            WHEN SUM(total_revenue) OVER (ORDER BY total_revenue DESC) 
                / SUM(total_revenue) OVER () <= {{ var('abc_a_threshold') }} 
            THEN 'A'
            WHEN SUM(total_revenue) OVER (ORDER BY total_revenue DESC) 
                / SUM(total_revenue) OVER () <= {{ var('abc_b_threshold') }} 
            THEN 'B'
            ELSE 'C'
        END AS abc_class
        
    FROM product_metrics
)

SELECT * FROM abc_classification
