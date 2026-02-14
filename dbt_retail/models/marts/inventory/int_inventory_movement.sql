{{
    config(
        materialized='ephemeral'
    )
}}

WITH transaction_details AS (
    SELECT * FROM {{ ref('stg_transaction_details') }}
),

daily_movement AS (
    SELECT
        transaction_date,
        product_code,
        product_name,
        brand,
        category_l1,
        category_l2,
        
        -- Xuất hàng (bán ra)
        SUM(quantity) AS units_sold,
        SUM(line_revenue) AS revenue,
        SUM(line_cost) AS cogs,
        SUM(line_profit) AS profit,
        
        COUNT(DISTINCT transaction_id) AS transaction_count
        
    FROM transaction_details
    GROUP BY 
        transaction_date,
        product_code,
        product_name,
        brand,
        category_l1,
        category_l2
)

SELECT * FROM daily_movement
