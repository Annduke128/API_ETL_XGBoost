{{
    config(
        materialized='table',
        tags=['ml', 'forecasting']
    )
}}

WITH daily_movement AS (
    SELECT * FROM {{ ref('int_inventory_movement') }}
),

-- Tính tồn kho tối thiểu dựa trên lịch sử bán hàng
inventory_stats AS (
    SELECT
        product_code,
        product_name,
        brand,
        category_l1,
        
        -- Thống kê bán hàng
        AVG(units_sold) AS avg_daily_sales,
        STDDEV(units_sold) AS std_daily_sales,
        MAX(units_sold) AS max_daily_sales,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY units_sold) AS p95_daily_sales,
        
        -- Doanh thu
        AVG(revenue) AS avg_daily_revenue,
        SUM(revenue) AS total_revenue,
        
        -- Ngày bán hàng
        COUNT(DISTINCT transaction_date) AS selling_days,
        MIN(transaction_date) AS first_sale,
        MAX(transaction_date) AS last_sale,
        
        -- Tính tốc độ bán hàng (velocity)
        SUM(units_sold)::FLOAT / NULLIF(COUNT(DISTINCT transaction_date), 0) AS sales_velocity
        
    FROM daily_movement
    WHERE transaction_date >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY product_code, product_name, brand, category_l1
),

forecast_input AS (
    SELECT
        *,
        
        -- Tồn kho tối thiểu đề xuất (safety stock)
        -- Công thức: (avg_daily_sales + 1.65 * std_daily_sales) * lead_time_days ^ 0.5
        -- Giả định lead time = 7 ngày
        CEIL((avg_daily_sales + 1.65 * COALESCE(std_daily_sales, 0)) * SQRT(7)) AS suggested_safety_stock,
        
        -- Điểm đặt hàng lại (reorder point)
        CEIL(avg_daily_sales * 14) AS suggested_reorder_point,
        
        -- Số lượng đặt hàng đề xuất (EOQ approximation)
        CEIL(SQRT(2 * avg_daily_sales * 30 * 100 / 0.1)) AS suggested_order_quantity,
        
        -- Phân loại tốc độ bán hàng
        CASE 
            WHEN sales_velocity >= 10 THEN 'Fast'
            WHEN sales_velocity >= 3 THEN 'Medium'
            WHEN sales_velocity > 0 THEN 'Slow'
            ELSE 'Dead'
        END AS velocity_class,
        
        -- Mức độ ổn định
        CASE 
            WHEN std_daily_sales / NULLIF(avg_daily_sales, 0) < 0.5 THEN 'Stable'
            WHEN std_daily_sales / NULLIF(avg_daily_sales, 0) < 1.0 THEN 'Variable'
            ELSE 'Erratic'
        END AS demand_pattern,
        
        CURRENT_TIMESTAMP AS etl_timestamp
        
    FROM inventory_stats
)

SELECT * FROM forecast_input
