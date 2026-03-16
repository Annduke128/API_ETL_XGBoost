{{
  config(
    materialized = 'table',
    engine = 'MergeTree()',
    order_by = ['transaction_date', 'product_code', 'branch_code'],
    partition_by = "toYYYYMM(transaction_date)",
    tags = ['marts', 'sales', 'ml', 'baseline']
  )
}}

SELECT 
    t.ngay AS transaction_date,
    toYYYYMMDD(t.ngay) AS date_key,
    td.ma_hang AS product_code,
    p.ma_hang AS product_id,
    t.ma_chi_nhanh AS branch_code,
    b.ma_chi_nhanh AS branch_id,
    count() AS transaction_count,
    sum(td.so_luong) AS quantity_sold,
    sum(td.thanh_tien) AS gross_revenue,
    sum(td.so_luong * 0) AS cost_of_goods_sold,
    sum(td.thanh_tien) AS gross_profit,
    avg(td.don_gia) AS avg_selling_price,
    avg(td.thanh_tien) AS avg_profit_per_unit,
    0 AS profit_margin,
    now() AS etl_timestamp,
    0 AS is_promotional_sale,
    'regular' AS sale_type
FROM {{ source('retail_source', 'raw_transaction_details') }} td
JOIN {{ source('retail_source', 'raw_transactions') }} t ON td.transaction_id = t.id
LEFT JOIN {{ source('retail_source', 'raw_products') }} p ON td.ma_hang = p.ma_hang
LEFT JOIN {{ source('retail_source', 'raw_branches') }} b ON t.ma_chi_nhanh = b.ma_chi_nhanh
WHERE lower(p.cap_1) NOT LIKE '%khuyến mại%' 
   AND lower(p.cap_1) NOT LIKE '%khuyen mai%'
GROUP BY t.ngay, td.ma_hang, p.ma_hang, t.ma_chi_nhanh, b.ma_chi_nhanh
