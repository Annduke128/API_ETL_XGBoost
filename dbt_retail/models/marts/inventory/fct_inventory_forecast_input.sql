{{
    config(
        materialized='table',
        tags = ['marts', 'ml', 'forecasting']
    )
}}

WITH daily_movement AS (
    SELECT
        t.ngay AS transaction_date,
        td.ma_hang AS product_code,
        COALESCE(td.ten_hang, '') AS product_name,
        SUM(td.so_luong) AS units_sold,
        SUM(td.thanh_tien) AS revenue
    FROM {{ source('retail_source', 'raw_transaction_details') }} td
    JOIN {{ source('retail_source', 'raw_transactions') }} t ON td.transaction_id = t.id
    GROUP BY t.ngay, td.ma_hang, td.ten_hang
),

inventory_stats AS (
    SELECT
        product_code,
        product_name,
        AVG(units_sold) AS avg_daily_sales,
        stddevPop(units_sold) AS std_daily_sales,
        MAX(units_sold) AS max_daily_sales,
        quantile(0.95)(units_sold) AS p95_daily_sales,
        AVG(revenue) AS avg_daily_revenue,
        SUM(revenue) AS total_revenue,
        COUNT(DISTINCT transaction_date) AS selling_days,
        MIN(transaction_date) AS first_sale,
        MAX(transaction_date) AS last_sale,
        SUM(units_sold)::FLOAT / NULLIF(COUNT(DISTINCT transaction_date), 0) AS sales_velocity
    FROM daily_movement
    WHERE transaction_date >= today() - toIntervalDay(90)
    GROUP BY product_code, product_name
)

SELECT
    product_code,
    product_name,
    avg_daily_sales,
    std_daily_sales,
    max_daily_sales,
    p95_daily_sales,
    avg_daily_revenue,
    total_revenue,
    selling_days,
    first_sale,
    last_sale,
    sales_velocity,
    CEIL((avg_daily_sales + 1.65 * COALESCE(std_daily_sales, 0)) * SQRT(7)) AS suggested_safety_stock,
    CEIL(avg_daily_sales * 14) AS suggested_reorder_point,
    CEIL(SQRT(2 * avg_daily_sales * 30 * 100 / 0.1)) AS suggested_order_quantity,
    CASE 
        WHEN sales_velocity >= 10 THEN 'Fast'
        WHEN sales_velocity >= 3 THEN 'Medium'
        WHEN sales_velocity > 0 THEN 'Slow'
        ELSE 'Dead'
    END AS velocity_class,
    CASE 
        WHEN std_daily_sales / NULLIF(avg_daily_sales, 0) < 0.5 THEN 'Stable'
        WHEN std_daily_sales / NULLIF(avg_daily_sales, 0) < 1.0 THEN 'Variable'
        ELSE 'Erratic'
    END AS demand_pattern,
    now() AS etl_timestamp
FROM inventory_stats
