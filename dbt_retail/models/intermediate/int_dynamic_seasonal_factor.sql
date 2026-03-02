{{
    config(
        materialized='view',
        tags=['intermediate', 'seasonality', 'ml_features'],
        description='Tính toán dynamic seasonal factor dựa trên dữ liệu lịch sử thực tế. So sánh doanh số ngày lễ/trong tuần với trung bình ngày thường cùng thởgian.'
    )
}}

-- Tính doanh số trung bình theo tháng và loại ngày (weekday vs weekend)
WITH monthly_baseline AS (
    SELECT 
        toMonth(transaction_date) AS month,
        -- Phân loại ngày: weekday (1-5) vs weekend (6-7)
        CASE 
            WHEN toDayOfWeek(transaction_date) IN (6, 7) THEN 'weekend'
            ELSE 'weekday'
        END AS day_type,
        AVG(gross_revenue) AS avg_daily_revenue,
        AVG(quantity_sold) AS avg_daily_quantity,
        COUNT(DISTINCT transaction_date) AS num_days
    FROM {{ ref('fct_regular_sales') }}
    WHERE transaction_date >= today() - 365  -- Lấy 1 năm gần nhất
    GROUP BY 
        toMonth(transaction_date),
        CASE 
            WHEN toDayOfWeek(transaction_date) IN (6, 7) THEN 'weekend'
            ELSE 'weekday'
        END
),

-- Tính doanh số thực tế cho các ngày đặc biệt (theo peak_reason từ seed)
peak_days_actual AS (
    SELECT 
        toMonth(f.transaction_date) AS month,
        s.peak_reason,
        AVG(f.gross_revenue) AS actual_avg_revenue,
        AVG(f.quantity_sold) AS actual_avg_quantity,
        COUNT(DISTINCT f.transaction_date) AS num_peak_days,
        -- Xác định loại ngày phổ biến nhất trong nhóm peak days
        mode(CASE 
            WHEN toDayOfWeek(f.transaction_date) IN (6, 7) THEN 'weekend'
            ELSE 'weekday'
        END) AS dominant_day_type
    FROM {{ ref('fct_regular_sales') }} f
    INNER JOIN {{ ref('seasonality_factors') }} s 
        ON toMonth(f.transaction_date) = s.month
    WHERE f.transaction_date >= today() - 365
    GROUP BY 
        toMonth(f.transaction_date),
        s.peak_reason
),

-- Tính dynamic factor: tỷ lệ giữa doanh số ngày đặc biệt vs baseline
dynamic_factors AS (
    SELECT 
        p.month,
        p.peak_reason,
        p.actual_avg_revenue,
        p.actual_avg_quantity,
        b.avg_daily_revenue AS baseline_revenue,
        b.avg_daily_quantity AS baseline_quantity,
        -- Dynamic factor cho revenue
        CASE 
            WHEN b.avg_daily_revenue > 0 
            THEN ROUND(p.actual_avg_revenue / b.avg_daily_revenue, 2)
            ELSE 1.0
        END AS revenue_factor,
        -- Dynamic factor cho quantity
        CASE 
            WHEN b.avg_daily_quantity > 0 
            THEN ROUND(p.actual_avg_quantity / b.avg_daily_quantity, 2)
            ELSE 1.0
        END AS quantity_factor,
        -- Factor tổng hợp (trung bình)
        CASE 
            WHEN b.avg_daily_revenue > 0 AND b.avg_daily_quantity > 0
            THEN ROUND((p.actual_avg_revenue / b.avg_daily_revenue + p.actual_avg_quantity / b.avg_daily_quantity) / 2, 2)
            ELSE 1.0
        END AS seasonal_factor,
        p.num_peak_days,
        b.day_type AS baseline_day_type
    FROM peak_days_actual p
    LEFT JOIN monthly_baseline b 
        ON p.month = b.month 
        AND p.dominant_day_type = b.day_type
)

SELECT 
    month,
    peak_reason,
    actual_avg_revenue,
    baseline_revenue,
    revenue_factor,
    quantity_factor,
    seasonal_factor,
    num_peak_days,
    baseline_day_type,
    -- Metadata cho debug
    now() AS calculated_at
FROM dynamic_factors
ORDER BY month
