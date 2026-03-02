{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['transaction_date', 'branch_code', 'product_code'],
        partition_by=['toYear(transaction_date)'],
        tags=['marts', 'sales', 'ml_features'],
        description='Bảng doanh số hàng ngày được enrich với dynamic seasonal factor cho ML training'
    )
}}

WITH daily_sales AS (
    SELECT *
    FROM {{ ref('fct_regular_sales') }}
),

-- Join với dynamic seasonal factor
seasonal_enriched AS (
    SELECT 
        d.*,
        -- Thông tin seasonality
        s.peak_reason,
        s.seasonal_factor,
        s.revenue_factor,
        s.quantity_factor,
        s.actual_avg_revenue AS seasonal_benchmark_revenue,
        s.baseline_revenue AS seasonal_baseline_revenue,
        -- Flag đánh dấu ngày đặc biệt
        CASE WHEN s.peak_reason IS NOT NULL THEN 1 ELSE 0 END AS is_peak_day,
        -- Month info từ seed
        CASE 
            WHEN toMonth(d.transaction_date) = 1 THEN 'Winter'
            WHEN toMonth(d.transaction_date) = 2 THEN 'Winter'
            WHEN toMonth(d.transaction_date) = 3 THEN 'Spring'
            WHEN toMonth(d.transaction_date) = 4 THEN 'Spring'
            WHEN toMonth(d.transaction_date) = 5 THEN 'Spring'
            WHEN toMonth(d.transaction_date) = 6 THEN 'Summer'
            WHEN toMonth(d.transaction_date) = 7 THEN 'Summer'
            WHEN toMonth(d.transaction_date) = 8 THEN 'Summer'
            WHEN toMonth(d.transaction_date) = 9 THEN 'Autumn'
            WHEN toMonth(d.transaction_date) = 10 THEN 'Autumn'
            WHEN toMonth(d.transaction_date) = 11 THEN 'Autumn'
            ELSE 'Winter'
        END AS season
    FROM daily_sales d
    LEFT JOIN {{ ref('int_dynamic_seasonal_factor') }} s
        ON toMonth(d.transaction_date) = s.month
)

SELECT *
FROM seasonal_enriched
