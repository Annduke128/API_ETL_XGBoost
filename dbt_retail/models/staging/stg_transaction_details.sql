{{
    config(
        materialized='view'
    )
}}

WITH source AS (
    SELECT * FROM {{ source('retail_source', 'transaction_details') }}
),

transactions AS (
    SELECT * FROM {{ source('retail_source', 'transactions') }}
),

products AS (
    SELECT * FROM {{ source('retail_source', 'products') }}
),

renamed AS (
    SELECT
        td.id AS detail_id,
        td.giao_dich_id AS transaction_id,
        t.ma_giao_dich,
        t.thoi_gian AS transaction_timestamp,
        DATE(t.thoi_gian) AS transaction_date,
        
        td.product_id,
        p.ma_hang AS product_code,
        p.ma_vach AS barcode,
        p.ten_hang AS product_name,
        p.thuong_hieu AS brand,
        p.nhom_hang_cap_1 AS category_l1,
        p.nhom_hang_cap_2 AS category_l2,
        p.nhom_hang_cap_3 AS category_l3,
        
        td.so_luong AS quantity,
        td.gia_ban AS selling_price,
        td.gia_von AS cost_price,
        td.loi_nhuan AS profit,
        
        -- Tổng giá trị
        td.so_luong * td.gia_ban AS line_revenue,
        td.so_luong * td.gia_von AS line_cost,
        td.so_luong * td.loi_nhuan AS line_profit,
        
        -- Phân loại
        CASE 
            WHEN td.gia_ban >= 1000000 THEN 'Premium'
            WHEN td.gia_ban >= 500000 THEN 'Standard'
            ELSE 'Economy'
        END AS price_segment,
        
        td.created_at
        
    FROM source td
    LEFT JOIN transactions t ON td.giao_dich_id = t.id
    LEFT JOIN products p ON td.product_id = p.id
)

SELECT * FROM renamed
