{{
    config(
        materialized='view'
    )
}}

WITH source AS (
    SELECT * FROM {{ source('retail_source', 'branches') }}
),

renamed AS (
    SELECT
        id AS branch_id,
        ma_chi_nhanh AS branch_code,
        ten_chi_nhanh AS branch_name,
        dia_chi AS address,
        thanh_pho AS city,
        
        -- Loại chi nhánh
        CASE 
            WHEN ten_chi_nhanh LIKE '%Flagship%' THEN 'Flagship'
            WHEN ten_chi_nhanh LIKE '%Mini%' THEN 'Mini'
            ELSE 'Standard'
        END AS branch_type,
        
        created_at
        
    FROM source
)

SELECT * FROM renamed
