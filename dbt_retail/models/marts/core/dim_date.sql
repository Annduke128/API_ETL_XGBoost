{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by='date_key'
    )
}}

WITH date_spine AS (
    -- Tạo danh sách ngày từ 2020-01-01 đến 2030-12-31
    -- ClickHouse syntax: arrayJoin(range(...)) hoặc dùng numbers
    SELECT 
        toDate('2020-01-01') + number AS date_day
    FROM numbers(4018)  -- 11 năm * 365 + leap days ≈ 4018 ngày
    WHERE toDate('2020-01-01') + number <= toDate('2030-12-31')
),

dim_date AS (
    SELECT
        toYYYYMMDD(date_day) AS date_key,
        date_day AS full_date,
        
        -- Năm
        toYear(date_day) AS year,
        concat('Năm ', toString(toYear(date_day))) AS year_name,
        
        -- Quý
        toQuarter(date_day) AS quarter,
        concat('Q', toString(toQuarter(date_day)), '-', toString(toYear(date_day))) AS quarter_name,
        
        -- Tháng
        toMonth(date_day) AS month,
        formatDateTime(date_day, '%m/%Y') AS month_name,
        
        -- Tuần
        toWeek(date_day) AS week_of_year,
        
        -- Ngày
        toDayOfMonth(date_day) AS day_of_month,
        toDayOfWeek(date_day) AS day_of_week,
        
        -- Tên ngày (ClickHouse: Monday=1, Sunday=7)
        CASE toDayOfWeek(date_day)
            WHEN 7 THEN 'Chủ nhật'
            WHEN 1 THEN 'Thứ hai'
            WHEN 2 THEN 'Thứ ba'
            WHEN 3 THEN 'Thứ tư'
            WHEN 4 THEN 'Thứ năm'
            WHEN 5 THEN 'Thứ sáu'
            WHEN 6 THEN 'Thứ bảy'
        END AS day_name,
        
        -- Cuối tuần (ClickHouse: 7=Sunday)
        day_of_week IN (6, 7) AS is_weekend,
        
        -- Đầu/cuối tháng
        toDayOfMonth(date_day) = 1 AS is_first_day_of_month,
        date_day = toStartOfMonth(date_day + toIntervalMonth(1)) - 1 AS is_last_day_of_month,
        
        -- Fiscal year (tùy chỉnh theo năm tài chính của bạn)
        CASE 
            WHEN toMonth(date_day) >= 4 
            THEN toYear(date_day)
            ELSE toYear(date_day) - 1
        END AS fiscal_year
        
    FROM date_spine
)

SELECT * FROM dim_date
