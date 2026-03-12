{{
    config(
        materialized='incremental',
        engine='MergeTree()',
        partition_by='toYYYYMM(month)',
        order_by=['month', 'product_code', 'branch_code'],
        unique_key=['month', 'product_code', 'branch_code'],
        incremental_strategy='delete+insert',
        tags=['marts', 'sales', 'monthly', 'incremental']
    )
}}

WITH daily_source AS (
    SELECT * FROM {{ ref('fct_daily_sales') }}
    {% if is_incremental() %}
    WHERE transaction_date >= (SELECT MAX(month) - 35 FROM {{ this }})
    {% endif %}
),

monthly_aggregated AS (
    SELECT
        toStartOfMonth(transaction_date) as month,
        toYYYYMM(transaction_date) as month_key,
        product_code,
        branch_code,
        SUM(daily_quantity) as monthly_quantity,
        SUM(daily_revenue) as monthly_revenue,
        SUM(daily_cost) as monthly_cost,
        SUM(daily_profit) as monthly_profit,
        AVG(daily_profit_margin) as avg_profit_margin,
        COUNT(DISTINCT transaction_date) as active_days,
        now() as etl_timestamp
    FROM daily_source
    GROUP BY toStartOfMonth(transaction_date), toYYYYMM(transaction_date), product_code, branch_code
)

SELECT * FROM monthly_aggregated
