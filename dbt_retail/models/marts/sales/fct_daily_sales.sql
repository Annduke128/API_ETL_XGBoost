{{
    config(
        materialized='table',
        unique_key=['date_key', 'branch_id', 'product_id'],
        partition_by={
            "field": "transaction_date",
            "data_type": "date",
            "granularity": "month"
        }
    )
}}

WITH transaction_details AS (
    SELECT * FROM {{ ref('stg_transaction_details') }}
),

daily_sales AS (
    SELECT
        td.transaction_date,
        CAST(TO_CHAR(td.transaction_date, 'YYYYMMDD') AS INTEGER) AS date_key,
        
        -- Product
        td.product_code,
        p.product_id,
        
        -- Branch (lấy từ transaction)
        t.branch_code,
        b.branch_id,
        
        -- Số liệu
        COUNT(DISTINCT td.transaction_id) AS transaction_count,
        SUM(td.quantity) AS quantity_sold,
        SUM(td.line_revenue) AS gross_revenue,
        SUM(td.line_cost) AS cost_of_goods_sold,
        SUM(td.line_profit) AS gross_profit,
        
        -- Metrics
        AVG(td.selling_price) AS avg_selling_price,
        AVG(td.profit) AS avg_profit_per_unit,
        
        -- Tỷ lệ
        CASE 
            WHEN SUM(td.line_revenue) > 0 
            THEN SUM(td.line_profit) / SUM(td.line_revenue) 
            ELSE 0 
        END AS profit_margin,
        
        -- Timestamp
        CURRENT_TIMESTAMP AS etl_timestamp
        
    FROM transaction_details td
    LEFT JOIN {{ ref('dim_product') }} p ON td.product_code = p.product_code
    LEFT JOIN {{ ref('stg_transactions') }} t ON td.transaction_id = t.transaction_id
    LEFT JOIN {{ ref('dim_branch') }} b ON t.branch_code = b.branch_code
    
    GROUP BY 
        td.transaction_date,
        td.product_code,
        p.product_id,
        t.branch_code,
        b.branch_id
)

SELECT * FROM daily_sales
