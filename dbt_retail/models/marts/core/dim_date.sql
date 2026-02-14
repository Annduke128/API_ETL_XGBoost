{{
    config(
        materialized='table',
        unique_key='date_key'
    )
}}

WITH date_spine AS (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="'2020-01-01'",
        end_date="'2030-12-31'"
    ) }}
),

dim_date AS (
    SELECT
        CAST(TO_CHAR(date_day, 'YYYYMMDD') AS INTEGER) AS date_key,
        date_day AS full_date,
        
        -- Năm
        EXTRACT(YEAR FROM date_day) AS year,
        CONCAT('Năm ', EXTRACT(YEAR FROM date_day)) AS year_name,
        
        -- Quý
        EXTRACT(QUARTER FROM date_day) AS quarter,
        CONCAT('Q', EXTRACT(QUARTER FROM date_day), '-', EXTRACT(YEAR FROM date_day)) AS quarter_name,
        
        -- Tháng
        EXTRACT(MONTH FROM date_day) AS month,
        TO_CHAR(date_day, 'MM/YYYY') AS month_name,
        
        -- Tuần
        EXTRACT(WEEK FROM date_day) AS week_of_year,
        
        -- Ngày
        EXTRACT(DAY FROM date_day) AS day_of_month,
        EXTRACT(DOW FROM date_day) AS day_of_week,
        
        -- Tên ngày
        CASE EXTRACT(DOW FROM date_day)
            WHEN 0 THEN 'Chủ nhật'
            WHEN 1 THEN 'Thứ hai'
            WHEN 2 THEN 'Thứ ba'
            WHEN 3 THEN 'Thứ tư'
            WHEN 4 THEN 'Thứ năm'
            WHEN 5 THEN 'Thứ sáu'
            WHEN 6 THEN 'Thứ bảy'
        END AS day_name,
        
        -- Cuối tuần
        CASE WHEN EXTRACT(DOW FROM date_day) IN (0, 6) THEN TRUE ELSE FALSE END AS is_weekend,
        
        -- Đầu/cuối tháng
        CASE WHEN EXTRACT(DAY FROM date_day) = 1 THEN TRUE ELSE FALSE END AS is_first_day_of_month,
        CASE 
            WHEN date_day = (date_day + INTERVAL '1 month' - INTERVAL '1 day')::date 
            THEN TRUE ELSE FALSE 
        END AS is_last_day_of_month,
        
        -- Fiscal year (tùy chỉnh theo năm tài chính của bạn)
        CASE 
            WHEN EXTRACT(MONTH FROM date_day) >= 4 
            THEN EXTRACT(YEAR FROM date_day)
            ELSE EXTRACT(YEAR FROM date_day) - 1
        END AS fiscal_year
        
    FROM date_spine
)

SELECT * FROM dim_date
