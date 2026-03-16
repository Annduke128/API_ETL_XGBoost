{{
  config(
    materialized = 'table',
    engine = 'MergeTree()',
    order_by = ['transaction_date', 'product_code', 'branch_code'],
    partition_by = "toYYYYMM(transaction_date)",
    tags = ['marts', 'sales', 'ml', 'promotion']
  )
}}
-- fct_promotional_sales: Promotional sales fact table
-- Source: staging tables từ PostgreSQL sync
SELECT 
    toDate(t.ngay) AS transaction_date,
    toYYYYMMDD(toDate(t.ngay)) AS date_key,
    td.ma_hang AS product_code,
    p.ma_hang AS product_id,
    t.ma_chi_nhanh AS branch_code,
    b.ma_chi_nhanh AS branch_id,
    count() AS transaction_count,
    sum(td.so_luong) AS quantity_sold,
    sum(td.thanh_tien) AS gross_revenue,
    sum(td.so_luong * COALESCE(p.gia_von_mac_dinh, 0)) AS cost_of_goods_sold,
    sum(td.thanh_tien) AS gross_profit,
    avg(td.don_gia) AS avg_selling_price,
    avg(td.thanh_tien) AS avg_profit_per_unit,
    CASE 
        WHEN sum(td.thanh_tien) > 0 
        THEN (sum(td.thanh_tien) - sum(td.so_luong * COALESCE(p.gia_von_mac_dinh, 0))) / sum(td.thanh_tien)
        ELSE 0 
    END AS profit_margin,
    now() AS etl_timestamp,
    p.cap_1 AS promotion_category,
    p.cap_2 AS promotion_subcategory,
    1 AS is_promotional_sale,
    'promotional' AS sale_type
FROM {{ source('retail_source', 'staging_transaction_details') }} td
JOIN {{ source('retail_source', 'staging_transactions') }} t 
    ON td.transaction_id = t.id
LEFT JOIN {{ source('retail_source', 'staging_products') }} p 
    ON td.ma_hang = p.ma_hang
LEFT JOIN {{ source('retail_source', 'staging_branches') }} b 
    ON t.ma_chi_nhanh = b.ma_chi_nhanh
WHERE lower(p.cap_1) LIKE '%khuyến mại%' 
   OR lower(p.cap_1) LIKE '%khuyen mai%'
GROUP BY 
    toDate(t.ngay), 
    td.ma_hang, 
    p.ma_hang, 
    t.ma_chi_nhanh, 
    b.ma_chi_nhanh, 
    p.cap_1, 
    p.cap_2
