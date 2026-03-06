{{
    config(
        materialized='view'
    )
}}

WITH transaction_details AS (
    SELECT * FROM {{ ref('stg_transaction_details') }}
),

transactions AS (
    SELECT 
        transaction_id,
        transaction_date
    FROM {{ ref('stg_transactions') }}
),

daily_movement AS (
    SELECT
        t.transaction_date,
        td.product_code,
        td.product_name,
        td.brand,
        td.category_l1,
        td.category_l2,
        
        -- Xuất hàng (bán ra)
        SUM(td.quantity) AS units_sold,
        SUM(td.line_revenue) AS revenue,
        SUM(td.line_cost) AS cogs,
        SUM(td.line_profit) AS profit,
        
        COUNT(DISTINCT td.transaction_id) AS transaction_count
        
    FROM transaction_details td
    JOIN transactions t ON td.transaction_id = t.transaction_id
    GROUP BY 
        t.transaction_date,
        td.product_code,
        td.product_name,
        td.brand,
        td.category_l1,
        td.category_l2
)

SELECT * FROM daily_movement
