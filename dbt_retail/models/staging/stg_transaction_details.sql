{{ config(materialized='view') }}

SELECT 
    toString(d.transaction_id) || '-' || d.ma_hang AS detail_id,
    toString(d.transaction_id) AS transaction_id,
    d.ma_hang AS product_code,
    d.ten_hang AS product_name,
    '' AS brand,
    '' AS category_l1,
    '' AS category_l2,
    d.so_luong AS quantity,
    d.don_gia AS unit_price,
    d.don_gia AS selling_price,
    d.chiet_khau AS discount_amount,
    d.thue_gtgt AS tax_amount,
    d.thanh_tien AS line_total,
    toFloat64(0) AS line_revenue,
    toFloat64(0) AS line_cost,
    toFloat64(0) AS line_profit,
    toFloat64(0) AS cost_price,
    t.transaction_date,
    t.branch_code
FROM {{ source('retail_source', 'raw_transaction_details') }} d
JOIN {{ ref('stg_transactions') }} t 
    ON d.transaction_id = t.id_num
