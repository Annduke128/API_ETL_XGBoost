{{
    config(
        materialized='ephemeral'
    )
}}

WITH transactions AS (
    SELECT * FROM {{ ref('stg_transactions') }}
),

branch_metrics AS (
    SELECT
        branch_code,
        branch_name,
        city,
        branch_type,
        
        -- Số liệu tổng hợp
        COUNT(DISTINCT transaction_id) AS total_transactions,
        SUM(revenue) AS total_revenue,
        SUM(gross_profit) AS total_profit,
        AVG(revenue) AS avg_transaction_value,
        
        -- Phân loại giao dịch
        SUM(CASE WHEN value_tier = 'High' THEN 1 ELSE 0 END) AS high_value_transactions,
        SUM(CASE WHEN value_tier = 'Medium' THEN 1 ELSE 0 END) AS medium_value_transactions,
        SUM(CASE WHEN value_tier = 'Low' THEN 1 ELSE 0 END) AS low_value_transactions,
        
        -- Ngày hoạt động
        MIN(transaction_date) AS first_transaction_date,
        MAX(transaction_date) AS last_transaction_date,
        COUNT(DISTINCT transaction_date) AS operating_days
        
    FROM transactions
    GROUP BY 1, 2, 3, 4
),

ranked AS (
    SELECT
        *,
        RANK() OVER (ORDER BY total_revenue DESC) AS revenue_rank,
        RANK() OVER (ORDER BY total_profit DESC) AS profit_rank,
        
        -- So sánh với trung bình
        total_revenue / AVG(total_revenue) OVER () AS revenue_vs_avg,
        total_profit / AVG(total_profit) OVER () AS profit_vs_avg
        
    FROM branch_metrics
)

SELECT * FROM ranked
