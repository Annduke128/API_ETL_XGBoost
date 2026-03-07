{{
    config(
        materialized='view',
        tags=['intermediate', 'seasonality', 'ml_features'],
        description='Tính toán dynamic seasonal factor với peak days và impact levels'
    )
}}

-- Tính doanh số trung bình theo tháng và loại ngày
WITH monthly_baseline AS (
    SELECT 
        toMonth(transaction_date) AS month,
        CASE 
            WHEN toDayOfWeek(transaction_date) IN (6, 7) THEN 'weekend'
            ELSE 'weekday'
        END AS day_type,
        AVG(gross_revenue) AS avg_daily_revenue,
        AVG(quantity_sold) AS avg_daily_quantity,
        COUNT(DISTINCT transaction_date) AS num_days
    FROM {{ ref('fct_regular_sales') }}
    WHERE transaction_date >= today() - 365
    GROUP BY 
        toMonth(transaction_date),
        CASE 
            WHEN toDayOfWeek(transaction_date) IN (6, 7) THEN 'weekend'
            ELSE 'weekday'
        END
),

-- Peak days với impact range
peak_days_with_range AS (
    SELECT 
        month,
        day,
        peak_reason,
        peak_level,
        impact_days,
        toDate(concat('2026-', toString(month), '-', toString(day))) as peak_date,
        toDate(concat('2026-', toString(month), '-', toString(day))) - INTERVAL impact_days DAY as impact_start_date,
        toDate(concat('2026-', toString(month), '-', toString(day))) + INTERVAL impact_days DAY as impact_end_date
    FROM {{ ref('stg_peak_days') }}
),

-- Sales với peak info (dùng WHERE thay vì JOIN ON)
sales_with_peak AS (
    SELECT 
        f.*,
        p.month AS peak_month,
        p.peak_reason,
        p.peak_level,
        p.impact_days,
        CASE 
            WHEN toDayOfWeek(f.transaction_date) IN (6, 7) THEN 'weekend'
            ELSE 'weekday'
        END AS day_type
    FROM {{ ref('fct_regular_sales') }} f
    CROSS JOIN peak_days_with_range p
    WHERE f.transaction_date >= today() - 365
      AND f.transaction_date >= p.impact_start_date 
      AND f.transaction_date <= p.impact_end_date
),

-- Tính doanh số thực tế cho các ngày trong impact range
peak_impact_actual AS (
    SELECT 
        toMonth(transaction_date) AS month,
        peak_reason,
        peak_level,
        impact_days,
        AVG(gross_revenue) AS actual_avg_revenue,
        AVG(quantity_sold) AS actual_avg_quantity,
        COUNT(DISTINCT transaction_date) AS num_peak_days,
        any(day_type) AS dominant_day_type
    FROM sales_with_peak
    GROUP BY 
        toMonth(transaction_date),
        peak_reason,
        peak_level,
        impact_days
),

-- Tính dynamic factor
dynamic_factors AS (
    SELECT 
        p.month,
        p.peak_reason,
        p.peak_level,
        p.impact_days,
        p.actual_avg_revenue,
        p.actual_avg_quantity,
        b.avg_daily_revenue AS baseline_revenue,
        b.avg_daily_quantity AS baseline_quantity,
        CASE 
            WHEN b.avg_daily_revenue > 0 
            THEN ROUND(p.actual_avg_revenue / b.avg_daily_revenue, 2)
            ELSE 1.0
        END AS revenue_factor,
        CASE 
            WHEN b.avg_daily_quantity > 0 
            THEN ROUND(p.actual_avg_quantity / b.avg_daily_quantity, 2)
            ELSE 1.0
        END AS quantity_factor,
        CASE 
            WHEN b.avg_daily_revenue > 0 AND b.avg_daily_quantity > 0
            THEN ROUND((p.actual_avg_revenue / b.avg_daily_revenue + p.actual_avg_quantity / b.avg_daily_quantity) / 2, 2)
            ELSE 1.0
        END AS seasonal_factor,
        p.num_peak_days,
        b.day_type AS baseline_day_type
    FROM peak_impact_actual p
    LEFT JOIN monthly_baseline b 
        ON p.month = b.month 
        AND p.dominant_day_type = b.day_type
)

SELECT 
    month,
    peak_reason,
    peak_level,
    impact_days,
    actual_avg_revenue,
    baseline_revenue,
    revenue_factor,
    quantity_factor,
    seasonal_factor,
    num_peak_days,
    baseline_day_type,
    CASE WHEN peak_level > 0 THEN 1 ELSE 0 END AS is_peak_day,
    now() AS calculated_at
FROM dynamic_factors
ORDER BY month, peak_level DESC
