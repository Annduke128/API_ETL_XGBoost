{{
    config(
        materialized='table',
        unique_key='branch_id'
    )
}}

WITH branches AS (
    SELECT * FROM {{ ref('stg_branches') }}
),

branch_performance AS (
    SELECT * FROM {{ ref('int_branch_performance') }}
),

dim_branch AS (
    SELECT
        b.branch_id,
        b.branch_code,
        b.branch_name,
        b.address,
        b.city,
        b.branch_type,
        
        -- Hiệu suất
        COALESCE(bp.total_historical_revenue, 0) AS total_historical_revenue,
        COALESCE(bp.total_historical_transactions, 0) AS total_historical_transactions,
        COALESCE(bp.avg_transaction_value, 0) AS avg_transaction_value,
        COALESCE(bp.revenue_rank, 0) AS revenue_rank,
        
        -- Phân loại hiệu suất
        CASE 
            WHEN bp.revenue_vs_avg >= 1.5 THEN 'Star'
            WHEN bp.revenue_vs_avg >= 1.0 THEN 'Standard'
            WHEN bp.revenue_vs_avg >= 0.5 THEN 'Developing'
            ELSE 'Underperforming'
        END AS performance_tier,
        
        b.created_at
        
    FROM branches b
    LEFT JOIN branch_performance bp ON b.branch_code = bp.branch_code
)

SELECT * FROM dim_branch
