{{
    config(
        materialized='table',
        tags=['kpi', 'reporting']
    )
}}

WITH daily_sales AS (
    SELECT * FROM {{ ref('fct_daily_sales') }}
),

date_dim AS (
    SELECT * FROM {{ ref('dim_date') }}
),

-- Tính các KPI chính
current_period AS (
    SELECT
        'Current Month' AS period,
        SUM(gross_revenue) AS revenue,
        SUM(gross_profit) AS profit,
        SUM(quantity_sold) AS quantity,
        SUM(transaction_count) AS transactions,
        AVG(profit_margin) AS avg_margin
    FROM daily_sales ds
    JOIN date_dim d ON ds.date_key = d.date_key
    WHERE d.year = EXTRACT(YEAR FROM CURRENT_DATE)
      AND d.month = EXTRACT(MONTH FROM CURRENT_DATE)
),

previous_period AS (
    SELECT
        'Previous Month' AS period,
        SUM(gross_revenue) AS revenue,
        SUM(gross_profit) AS profit,
        SUM(quantity_sold) AS quantity,
        SUM(transaction_count) AS transactions,
        AVG(profit_margin) AS avg_margin
    FROM daily_sales ds
    JOIN date_dim d ON ds.date_key = d.date_key
    WHERE d.year = EXTRACT(YEAR FROM CURRENT_DATE - INTERVAL '1 month')
      AND d.month = EXTRACT(MONTH FROM CURRENT_DATE - INTERVAL '1 month')
),

ytd AS (
    SELECT
        'YTD' AS period,
        SUM(gross_revenue) AS revenue,
        SUM(gross_profit) AS profit,
        SUM(quantity_sold) AS quantity,
        SUM(transaction_count) AS transactions,
        AVG(profit_margin) AS avg_margin
    FROM daily_sales ds
    JOIN date_dim d ON ds.date_key = d.date_key
    WHERE d.year = EXTRACT(YEAR FROM CURRENT_DATE)
      AND d.full_date <= CURRENT_DATE
),

kpi_summary AS (
    SELECT * FROM current_period
    UNION ALL
    SELECT * FROM previous_period
    UNION ALL
    SELECT * FROM ytd
)

SELECT
    period,
    revenue,
    profit,
    quantity,
    transactions,
    avg_margin,
    
    -- Tính toán thêm
    CASE WHEN transactions > 0 THEN revenue / transactions ELSE 0 END AS avg_transaction_value,
    CASE WHEN quantity > 0 THEN revenue / quantity ELSE 0 END AS avg_unit_price,
    
    CURRENT_TIMESTAMP AS report_timestamp
    
FROM kpi_summary
