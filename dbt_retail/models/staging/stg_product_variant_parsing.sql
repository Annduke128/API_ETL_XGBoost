{{
  config(
    materialized = 'view'
  )
}}

/*
    Staging model: Parse product_name theo logic 3 bước
    
    Logic (đã thống nhất):
    1. Pack info: Chỉ từ trong () ở cuối tên
    2. Weight: Số có đơn vị đo (g, kg, ml, l), chấp nhận cả . và ,
    3. Clean name: Tất cả còn lại (giữ "hương vị", số ngoài ngoặc, v.v.)
    
    ClickHouse Functions:
    - extract(haystack, pattern): Extract first match
    - REGEXP_REPLACE(haystack, pattern, replacement): Replace regex
*/

WITH product_base AS (
    SELECT 
        product_id,
        product_code,
        product_name,
        brand,
        category_level_1,
        category_level_2,
        category_level_3,
        default_selling_price
    FROM {{ ref('stg_products') }}
),

product_parsed AS (
    SELECT 
        *,
        
        -- ============================================
        -- 1. EXTRACT PACKAGING TYPE (trong ngoặc đơn ở cuối)
        -- ============================================
        -- Chỉ lấy nội dung trong () ở cuối tên
        extract(product_name, '\s*\(([^)]+)\)\s*$') as packaging_type,
        
        -- ============================================
        -- 2. EXTRACT WEIGHT/UNIT
        -- ============================================
        -- Pattern: số + đơn vị đo, chấp nhận cả . và , làm decimal
        -- Ví dụ: 700g, 0.35kg, 0,35kg, 1.5l, 500ml
        extract(product_name, '(\d+(?:[.,]\d+)?)\s*(g|kg|ml|l|G|KG|ML|L)\b') as weight_raw,
        
        -- Extract numeric part (weight value)
        extract(product_name, '(\d+(?:[.,]\d+)?)\s*(?:g|kg|ml|l|G|KG|ML|L)\b') as weight_value_str,
        
        -- Extract unit part
        upper(extract(product_name, '(?:\d+(?:[.,]\d+)?)\s*(g|kg|ml|l|G|KG|ML|L)\b')) as weight_unit,
        
        -- ============================================
        -- 3. BUILD CLEAN NAME
        -- ============================================
        -- Bước 1: Xóa pack info trong ngoặc () ở cuối
        REGEXP_REPLACE(product_name, '\s*\([^)]+\)\s*$', '') as name_no_packaging,
        
        -- Bước 2: Xóa weight (số + đơn vị đo)
        -- Pattern: số + khoảng trắng + đơn vị đo (g, kg, ml, l)
        REGEXP_REPLACE(
            REGEXP_REPLACE(product_name, '\s*\([^)]+\)\s*$', ''),
            '\s*\d+(?:[.,]\d+)?\s*(?:g|kg|ml|l|G|KG|ML|L)\b',
            ' '
        ) as clean_name_dirty
        
    FROM product_base
)

SELECT 
    product_id,
    product_code,
    product_name,
    brand,
    category_level_1,
    category_level_2,
    category_level_3,
    default_selling_price,
    
    -- Clean Name (đã xóa weight và packaging, giữ lại tất cả còn lại)
    trim(REGEXP_REPLACE(clean_name_dirty, '\s+', ' ')) as clean_name,
    
    -- Packaging Type
    packaging_type,
    
    -- Weight (chuẩn hóa về float, thay , thành .)
    CASE 
        WHEN weight_value_str != '' 
        THEN toFloat64OrNull(replace(weight_value_str, ',', '.'))
        ELSE NULL
    END as weight,
    
    -- Unit (chuẩn hóa về lowercase)
    CASE 
        WHEN weight_unit IN ('G', 'GR', 'GRAM') THEN 'g'
        WHEN weight_unit IN ('KG') THEN 'kg'
        WHEN weight_unit IN ('ML') THEN 'ml'
        WHEN weight_unit IN ('L') THEN 'l'
        ELSE NULL
    END as unit,
    
    -- Weight chuẩn hóa về cùng đơn vị (g hoặc ml)
    CASE 
        WHEN weight_unit IN ('G', 'GR', 'GRAM') THEN toFloat64OrNull(replace(weight_value_str, ',', '.'))
        WHEN weight_unit IN ('KG') THEN toFloat64OrNull(replace(weight_value_str, ',', '.')) * 1000
        WHEN weight_unit IN ('ML') THEN toFloat64OrNull(replace(weight_value_str, ',', '.'))
        WHEN weight_unit IN ('L') THEN toFloat64OrNull(replace(weight_value_str, ',', '.')) * 1000
        ELSE NULL
    END as weight_normalized_g_or_ml

FROM product_parsed
WHERE product_name IS NOT NULL
ORDER BY clean_name, weight_normalized_g_or_ml
