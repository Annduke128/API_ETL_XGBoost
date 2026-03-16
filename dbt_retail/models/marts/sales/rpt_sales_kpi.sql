{{
    config(
        materialized='table',
        tags = ['marts', 'kpi', 'reporting']
    )
}}
-- rpt_sales_kpi: Sales KPI summary report
-- Source: staging tables từ PostgreSQL sync
WITH daily_sales AS (
    SELECT
        toDate(t.ngay) AS transaction_date,
        toYYYYMMDD(toDate(t.ngay)) AS date_key,
        SUM(td.thanh_tien) AS gross_revenue,
        SUM(td.so_luong) AS quantity_sold,
        COUNT(DISTINCT td.transaction_id) AS transaction_count
    FROM {{ source('retail_source', 'staging_transaction_details') }} td
    JOIN {{ source('retail_source', 'staging_transactions') }} t 
        ON td.transaction_id = t.id
    GROUP BY toDate(t.ngay)
),

current_period AS (
    SELECT
        'Current Month' AS period,
        SUM(gross_revenue) AS revenue,
        SUM(quantity_sold) AS quantity,
        SUM(transaction_count) AS transactions
    FROM daily_sales
    WHERE toYear(transaction_date) = toYear(today())
      AND toMonth(transaction_date) = toMonth(today())
),

previous_period AS (
    SELECT
        'Previous Month' AS period,
        SUM(gross_revenue) AS revenue,
        SUM(quantity_sold) AS quantity,
        SUM(transaction_count) AS transactions
    FROM daily_sales
    WHERE toYear(transaction_date) = toYear(today() - toIntervalMonth(1))
      AND toMonth(transaction_date) = toMonth(today() - toIntervalMonth(1))
),

ytd AS (
    SELECT
        'YTD' AS period,
        SUM(gross_revenue) AS revenue,
        SUM(quantity_sold) AS quantity,
        SUM(transaction_count) AS transactions
    FROM daily_sales
    WHERE toYear(transaction_date) = toYear(today())
      AND transaction_date <= today()
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
    quantity,
    transactions,
    CASE WHEN transactions > 0 THEN revenue / transactions ELSE 0 END AS avg_transaction_value,
    CASE WHEN quantity > 0 THEN revenue / quantity ELSE 0 END AS avg_unit_price,
    now() AS report_timestamp
FROM kpi_summary
