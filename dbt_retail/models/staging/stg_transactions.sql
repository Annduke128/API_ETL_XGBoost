{{
    config(
        materialized='view',
        unique_key='transaction_id'
    )
}}

WITH source AS (
    SELECT * FROM {{ source('retail_source', 'transactions') }}
),

branches AS (
    SELECT * FROM {{ source('retail_source', 'branches') }}
),

renamed AS (
    SELECT
        t.id AS transaction_id,
        t.ma_giao_dich,
        t.chi_nhanh_id,
        b.ma_chi_nhanh,
        b.ten_chi_nhanh,
        t.thoi_gian AS transaction_timestamp,
        DATE(t.thoi_gian) AS transaction_date,
        EXTRACT(YEAR FROM t.thoi_gian) AS year,
        EXTRACT(MONTH FROM t.thoi_gian) AS month,
        EXTRACT(DOW FROM t.thoi_gian) AS day_of_week,
        EXTRACT(HOUR FROM t.thoi_gian) AS hour_of_day,
        
        -- Tài chính
        t.tong_tien_hang AS gross_amount,
        t.giam_gia AS discount_amount,
        t.doanh_thu AS revenue,
        t.tong_gia_von AS cost_amount,
        t.loi_nhuan_gop AS gross_profit,
        
        -- Tỷ lệ
        CASE 
            WHEN t.tong_tien_hang > 0 
            THEN t.giam_gia / t.tong_tien_hang 
            ELSE 0 
        END AS discount_rate,
        
        CASE 
            WHEN t.doanh_thu > 0 
            THEN t.loi_nhuan_gop / t.doanh_thu 
            ELSE 0 
        END AS profit_margin,
        
        -- Phân loại giá trị giao dịch
        CASE 
            WHEN t.doanh_thu >= {{ var('high_value_threshold') }} THEN 'High'
            WHEN t.doanh_thu >= {{ var('high_value_threshold') }} * 0.5 THEN 'Medium'
            ELSE 'Low'
        END AS value_tier,
        
        t.created_at
        
    FROM source t
    LEFT JOIN branches b ON t.chi_nhanh_id = b.id
)

SELECT * FROM renamed
