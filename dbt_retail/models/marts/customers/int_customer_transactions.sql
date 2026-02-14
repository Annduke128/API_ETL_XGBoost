{{
    config(
        materialized='ephemeral'
    )
}}

-- Trong ngành bán lẻ, "khách hàng" có thể được xác định qua mã giao dịch (giả định)
-- Hoặc có thể mở rộng để tích hợp với CRM

WITH transactions AS (
    SELECT * FROM {{ ref('stg_transactions') }}
),

customer_metrics AS (
    SELECT
        -- Giả định: mỗi giao dịch là một "khách hàng" cho POS bán lẻ
        -- Trong thực tế, cần tích hợp với loyalty card hoặc CRM
        ma_giao_dich AS customer_id,
        
        branch_code,
        city,
        region,
        
        -- Thờigian
        transaction_timestamp,
        transaction_date,
        hour_of_day,
        day_of_week,
        
        -- Tài chính
        revenue,
        gross_profit,
        discount_amount,
        
        -- Số lượng sản phẩm (cần join với details)
        1 AS item_count
        
    FROM transactions
)

SELECT * FROM customer_metrics
