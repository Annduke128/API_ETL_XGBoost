{{
    config(
        materialized='table',
        tags=['rfm', 'segmentation']
    )
}}

WITH customer_base AS (
    SELECT 
        branch_code AS customer_id,  -- Tạm thời dùng branch_code làm proxy
        transaction_date,
        revenue,
        gross_profit
    FROM {{ ref('stg_transactions') }}
),

rfm_base AS (
    SELECT
        customer_id,
        
        -- Recency: Số ngày kể từ lần mua cuối
        CURRENT_DATE - MAX(transaction_date) AS recency_days,
        
        -- Frequency: Số lần mua
        COUNT(DISTINCT transaction_date) AS frequency,
        
        -- Monetary: Tổng chi tiêu
        SUM(revenue) AS monetary,
        AVG(revenue) AS avg_order_value,
        
        -- Profit
        SUM(gross_profit) AS total_profit
        
    FROM customer_base
    WHERE transaction_date >= CURRENT_DATE - INTERVAL '365 days'
    GROUP BY customer_id
),

rfm_scored AS (
    SELECT
        *,
        
        -- Scores 1-5 (5 là tốt nhất)
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        NTILE(5) OVER (ORDER BY frequency) AS f_score,
        NTILE(5) OVER (ORDER BY monetary) AS m_score,
        
        -- Tổng điểm RFM
        NTILE(5) OVER (ORDER BY recency_days DESC) * 100 +
        NTILE(5) OVER (ORDER BY frequency) * 10 +
        NTILE(5) OVER (ORDER BY monetary) AS rfm_score
        
    FROM rfm_base
),

rfm_segmented AS (
    SELECT
        *,
        
        -- Phân khúc RFM
        CASE 
            -- Champions: R cao, F cao, M cao
            WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
            
            -- Loyal Customers: R cao, F cao, M trung bình
            WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 2 THEN 'Loyal Customers'
            
            -- Potential Loyalists: R cao, F trung bình
            WHEN r_score >= 4 AND f_score >= 2 THEN 'Potential Loyalists'
            
            -- New Customers: R cao, F thấp
            WHEN r_score >= 4 AND f_score <= 2 THEN 'New Customers'
            
            -- Promising: R trung bình, F thấp
            WHEN r_score >= 3 AND f_score <= 2 THEN 'Promising'
            
            -- Need Attention: R trung bình, F trung bình
            WHEN r_score >= 3 AND f_score >= 3 THEN 'Need Attention'
            
            -- About to Sleep: R thấp, F trung bình
            WHEN r_score >= 2 AND f_score >= 2 THEN 'About to Sleep'
            
            -- At Risk: R thấp, F cao
            WHEN r_score <= 2 AND f_score >= 4 THEN 'At Risk'
            
            -- Cannot Lose Them: R thấp, F cao, M cao
            WHEN r_score <= 2 AND f_score >= 4 AND m_score >= 4 THEN 'Cannot Lose Them'
            
            -- Hibernating: R thấp, F thấp
            WHEN r_score <= 2 AND f_score <= 2 THEN 'Hibernating'
            
            -- Lost: R rất thấp
            ELSE 'Lost'
        END AS rfm_segment,
        
        -- Chiến lược tiếp cận
        CASE 
            WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 
                THEN 'Reward them, early adopter for new products'
            WHEN r_score >= 4 AND f_score >= 4 
                THEN 'Upsell higher value products'
            WHEN r_score >= 4 AND f_score >= 2 
                THEN 'Offer membership/loyalty program'
            WHEN r_score >= 4 AND f_score <= 2 
                THEN 'Make them familiar, nurture them'
            WHEN r_score >= 3 AND f_score <= 2 
                THEN 'Offer free trials, build trust'
            WHEN r_score >= 3 AND f_score >= 3 
                THEN 'Make limited time offers'
            WHEN r_score >= 2 AND f_score >= 2 
                THEN 'Share valuable resources'
            WHEN r_score <= 2 AND f_score >= 4 
                THEN 'Send personalized reactivation campaigns'
            WHEN r_score <= 2 AND f_score >= 4 AND m_score >= 4 
                THEN 'Win them back via renewals/helpful products'
            WHEN r_score <= 2 AND f_score <= 2 
                THEN 'Offer discounts/win-back campaigns'
            ELSE 'Ignore'
        END AS recommended_action,
        
        CURRENT_TIMESTAMP AS etl_timestamp
        
    FROM rfm_scored
)

SELECT * FROM rfm_segmented
