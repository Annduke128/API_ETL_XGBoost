{{
    config(
        materialized='view'
    )
}}

WITH source AS (
    SELECT * FROM {{ source('retail_source', 'products') }}
),

renamed AS (
    SELECT
        id AS product_id,
        ma_hang AS product_code,
        ma_vach AS barcode,
        ten_hang AS product_name,
        thuong_hieu AS brand,
        
        -- Phân loại 3 cấp
        nhom_hang_cap_1 AS category_level_1,
        nhom_hang_cap_2 AS category_level_2,
        nhom_hang_cap_3 AS category_level_3,
        
        -- Giá
        gia_von_mac_dinh AS default_cost_price,
        gia_ban_mac_dinh AS default_selling_price,
        
        -- Biên lợi nhuận mặc định
        CASE 
            WHEN gia_ban_mac_dinh > 0 
            THEN (gia_ban_mac_dinh - gia_von_mac_dinh) / gia_ban_mac_dinh 
            ELSE 0 
        END AS default_margin_rate,
        
        created_at,
        updated_at
        
    FROM source
)

SELECT * FROM renamed
