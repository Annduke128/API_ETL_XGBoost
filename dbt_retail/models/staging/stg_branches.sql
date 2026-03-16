{{ config(materialized='view') }}
SELECT 
    ma_chi_nhanh AS branch_id, ma_chi_nhanh AS branch_code, ten_chi_nhanh AS branch_name,
    '' AS address, city, 'Standard' AS branch_type, now() AS created_at
FROM {{ source('retail_source', 'raw_branches') }}
GROUP BY ma_chi_nhanh, ten_chi_nhanh, city
