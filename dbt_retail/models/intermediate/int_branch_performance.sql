{{
    config(
        materialized='ephemeral'
    )
}}

WITH transactions AS (
    SELECT * FROM {{ ref('stg_transactions') }}
),

branches AS (
    SELECT * FROM {{ ref('stg_branches') }}
),

branch_metrics AS (
    SELECT
        t.branch_code,
        b.branch_name,
        b.city,
        b.branch_type,
        
        -- Số liệu tổng hợp
        COUNT(DISTINCT t.transaction_id) AS total_transactions,
        SUM(t.revenue) AS total_revenue,
        SUM(t.gross_profit) AS total_profit,
        AVG(t.revenue) AS avg_transaction_value,
        
        -- Phân loại giao dịch (todo: add value_tier calculation)
        0 AS high_value_transactions,
        0 AS medium_value_transactions,
        0 AS low_value_transactions,
        
        -- Ngày hoạt động
        MIN(t.transaction_date) AS first_transaction_date,
        MAX(t.transaction_date) AS last_transaction_date,
        COUNT(DISTINCT t.transaction_date) AS operating_days
        
    FROM transactions t
    LEFT JOIN branches b ON t.branch_code = b.branch_code
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
