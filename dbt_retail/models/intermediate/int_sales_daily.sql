{{
    config(
        materialized='ephemeral'
    )
}}

WITH transaction_details AS (
    SELECT * FROM {{ ref('stg_transaction_details') }}
),

daily_summary AS (
    SELECT
        transaction_date,
        product_code,
        product_name,
        brand,
        category_l1,
        category_l2,
        category_l3,
        
        -- Số liệu tổng hợp
        COUNT(DISTINCT transaction_id) AS transaction_count,
        SUM(quantity) AS total_quantity,
        SUM(line_revenue) AS total_revenue,
        SUM(line_cost) AS total_cost,
        SUM(line_profit) AS total_profit,
        
        -- Giá trị trung bình
        AVG(selling_price) AS avg_selling_price,
        AVG(quantity) AS avg_quantity_per_transaction
        
    FROM transaction_details
    GROUP BY 1, 2, 3, 4, 5, 6, 7
)

SELECT * FROM daily_summary
