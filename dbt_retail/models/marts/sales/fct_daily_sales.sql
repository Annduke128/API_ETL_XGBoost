{{
    config(
        materialized='table',
        engine='MergeTree()',
        tags=['marts']
    )
}}

WITH transaction_details AS (
    SELECT * FROM {{ ref('stg_transaction_details') }}
),

transactions AS (
    SELECT 
        transaction_id,
        transaction_date,
        branch_code
    FROM {{ ref('stg_transactions') }}
),

td_with_date AS (
    SELECT 
        td.*,
        t.transaction_date,
        t.branch_code
    FROM transaction_details td
    JOIN transactions t ON td.transaction_id = t.transaction_id
),

daily_sales AS (
    SELECT
        td.transaction_date AS transaction_date,
        toYYYYMMDD(td.transaction_date) AS date_key,
        
        -- Product
        td.product_code AS product_code,
        p.product_id AS product_id,
        
        -- Branch
        td.branch_code AS branch_code,
        b.branch_id AS branch_id,
        
        -- Số liệu
        COUNT(DISTINCT td.transaction_id) AS transaction_count,
        SUM(td.quantity) AS quantity_sold,
        SUM(td.line_revenue) AS gross_revenue,
        SUM(td.line_cost) AS cost_of_goods_sold,
        SUM(td.line_profit) AS gross_profit,
        
        -- Metrics
        AVG(td.selling_price) AS avg_selling_price,
        AVG(td.line_profit) AS avg_profit_per_unit,
        
        -- Tỷ lệ
        CASE 
            WHEN SUM(td.line_revenue) > 0 
            THEN SUM(td.line_profit) / SUM(td.line_revenue) 
            ELSE 0 
        END AS profit_margin,
        
        -- Timestamp
        now() AS etl_timestamp
        
    FROM td_with_date td
    LEFT JOIN {{ ref('dim_product') }} p ON td.product_code = p.product_code
    LEFT JOIN {{ ref('dim_branch') }} b ON td.branch_code = b.branch_code
    
    GROUP BY 
        td.transaction_date,
        td.product_code,
        p.product_id,
        td.branch_code,
        b.branch_id
)

SELECT * FROM daily_sales
