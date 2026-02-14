{{
    config(
        materialized='table',
        unique_key=['year_month', 'branch_id', 'product_id']
    )
}}

WITH daily_sales AS (
    SELECT * FROM {{ ref('fct_daily_sales') }}
),

monthly_sales AS (
    SELECT
        TO_CHAR(transaction_date, 'YYYY-MM') AS year_month,
        DATE_TRUNC('month', transaction_date)::date AS month_start_date,
        
        product_id,
        branch_id,
        
        -- Số liệu tổng hợp
        SUM(transaction_count) AS total_transactions,
        SUM(quantity_sold) AS total_quantity,
        SUM(gross_revenue) AS total_gross_revenue,
        SUM(cost_of_goods_sold) AS total_cogs,
        SUM(gross_profit) AS total_gross_profit,
        
        -- Trung bình
        AVG(avg_selling_price) AS avg_selling_price,
        AVG(profit_margin) AS avg_profit_margin,
        
        -- So sánh tháng trước (sẽ được tính trong BI layer)
        CURRENT_TIMESTAMP AS etl_timestamp
        
    FROM daily_sales
    GROUP BY 
        TO_CHAR(transaction_date, 'YYYY-MM'),
        DATE_TRUNC('month', transaction_date)::date,
        product_id,
        branch_id
)

SELECT * FROM monthly_sales
