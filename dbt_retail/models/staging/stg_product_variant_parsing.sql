{{
  config(
    materialized = 'view'
  )
}}

/*
    Staging model: Phân tích product_name để tách variant attributes
    
    Input: stg_products.product_name
    Output: Các trường phân tách (product_family, variant_size, packaging_type...)
    
    Patterns xử lý:
    1. Weight/Volume: 500g, 200g, 1500ml, 320ML, 30G
    2. Pack Size: 30 gói, 24 ly, 12 thố, x48, 180mlx48
    3. Flavor/Variant: Vị Cay ngọt, Hương Cam, giảm đường
    4. Packaging: (Gói), (Hộp), (Chai), (Lon), (Cái), (Túi), (Bát), (Ly)
    
    ClickHouse Functions:
    - extract(haystack, pattern): Extract first match
    - extractAll(haystack, pattern): Extract all matches
    - REGEXP_REPLACE(haystack, pattern, replacement): Replace regex
    - arrayJoin(array): Unnest array to rows
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
        -- 1. EXTRACT PACKAGING TYPE (trong ngoặc đơn)
        -- ============================================
        arrayJoin(extractAll(product_name, '\\(([^)]+)\\)')) as packaging_raw,
        
        -- ============================================
        -- 2. EXTRACT WEIGHT/VOLUME
        -- ============================================
        -- Extract full pattern: "500g", "200ml", "1.5L"
        extract(product_name, '\\d+(?:\\.\\d+)?\\s*(?:g|gr|gram|kg|ml|l|L|ML|G)') as weight_volume_raw,
        -- Extract numeric part
        extract(product_name, '\\d+(?:\\.\\d+)?') as weight_volume_numeric,
        -- Extract unit part
        upper(extract(product_name, '(?:\\d+(?:\\.\\d+)?)\\s*(g|gr|gram|kg|ml|l|L|ML|G)')) as weight_volume_unit,
        
        -- ============================================
        -- 3. EXTRACT PACK SIZE (số lượng trong pack)
        -- ============================================
        -- Pack count (số gói/lon/chai trong 1 hộp/thùng)
        extract(product_name, '\\d+\\s*(?:gói|ly|thố|hộp|lon|chai|stick)') as pack_count_raw,
        extract(product_name, '\\d+') as pack_count_numeric,
        
        -- Multipack pattern: 12(4x110ml) -> outer=12, inner=4
        extract(product_name, '\\d+\\s*\\(\\s*\\d+\\s*x\\s*\\d+') as outer_pack_raw,
        
        -- Pattern: 180mlx48, 110ml*48
        extract(product_name, '(?:\\d+\\s*(?:ml|g|ML|G))\\s*[xX*×]\\s*\\d+') as combo_pack_raw,
        extract(product_name, '(?:\\d+\\s*(?:ml|g|ML|G))\\s*[xX*×]\\s*(\\d+)') as combo_multiplier,
        
        -- ============================================
        -- 4. EXTRACT FLAVOR/VARIANT
        -- ============================================
        -- Flavor patterns
        extract(product_name, '[Vv]ị\\s+([^\\(]+?)(?=\\s+\\d|\\s*\\(|$)') as flavor_raw,
        extract(product_name, '[Hh]ương\\s+([^\\(]+?)(?=\\s+\\d|\\s*\\(|$)') as scent_raw,
        
        -- Variant keywords
        CASE 
            WHEN product_name ILIKE '%giảm đường%' OR product_name ILIKE '%ít đường%' THEN 'Low Sugar'
            WHEN product_name ILIKE '%không đường%' THEN 'Sugar Free'
            WHEN product_name ILIKE '%có thạch%' THEN 'With Jelly'
            WHEN product_name ILIKE '%cay ngọt%' THEN 'Sweet Spicy'
            WHEN product_name ILIKE '%cay%' THEN 'Spicy'
            ELSE NULL
        END as variant_feature,
        
        -- ============================================
        -- 5. BUILD PRODUCT FAMILY (tên gốc, bỏ variant)
        -- ============================================
        -- Bước 1: Loại bỏ packaging trong ngoặc
        REGEXP_REPLACE(product_name, '\\s*\\([^)]+\\)\\s*\$', '') as name_no_packaging,
        
        -- Bước 2: Loại bỏ weight/volume
        REGEXP_REPLACE(
            REGEXP_REPLACE(product_name, '\\s*\\([^)]+\\)\\s*\$', ''),
            '\\s*\\d+(?:\\.\\d+)?\\s*(?:g|gr|gram|kg|ml|l|L|ML|G)',
            ' '
        ) as name_no_size,
        
        -- Bước 3: Loại bỏ pack count
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                REGEXP_REPLACE(product_name, '\\s*\\([^)]+\\)\\s*\$', ''),
                '\\s*\\d+(?:\\.\\d+)?\\s*(?:g|gr|gram|kg|ml|l|L|ML|G)',
                ' '
            ),
            '\\s*\\d+\\s*(?:gói|ly|thố|hộp|lon|chai|stick)',
            ' '
        ) as name_no_pack_count,
        
        -- Bước 4: Loại bỏ flavor
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                REGEXP_REPLACE(
                    REGEXP_REPLACE(product_name, '\\s*\\([^)]+\\)\\s*\$', ''),
                    '\\s*\\d+(?:\\.\\d+)?\\s*(?:g|gr|gram|kg|ml|l|L|ML|G)',
                    ' '
                ),
                '\\s*\\d+\\s*(?:gói|ly|thố|hộp|lon|chai|stick)',
                ' '
            ),
            '\\s*[Vv]ị\\s+[^\\(]+?(?=\\s+\\d|\\s*\\(|$)',
            ' '
        ) as product_family_dirty
        
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
    
    -- Product Family (cleaned)
    trim(REGEXP_REPLACE(product_family_dirty, '\\s+', ' ')) as product_family,
    
    -- Size Information
    weight_volume_raw as size_raw,
    toFloat32OrNull(weight_volume_numeric) as size_value,
    CASE 
        WHEN weight_volume_unit IN ('G', 'GR', 'GRAM') THEN 'g'
        WHEN weight_volume_unit IN ('KG') THEN 'kg'
        WHEN weight_volume_unit IN ('ML') THEN 'ml'
        WHEN weight_volume_unit IN ('L') THEN 'l'
    END as size_unit,
    
    -- Chuẩn hóa về cùng đơn vị để so sánh (đổi về gram hoặc ml)
    CASE 
        WHEN weight_volume_unit IN ('G', 'GR', 'GRAM') THEN toFloat32OrNull(weight_volume_numeric)
        WHEN weight_volume_unit IN ('KG') THEN toFloat32OrNull(weight_volume_numeric) * 1000
        WHEN weight_volume_unit IN ('ML') THEN toFloat32OrNull(weight_volume_numeric)
        WHEN weight_volume_unit IN ('L') THEN toFloat32OrNull(weight_volume_numeric) * 1000
    END as size_normalized_ml_or_g,
    
    -- Pack Information
    packaging_raw as packaging_type,
    toInt32OrNull(pack_count_numeric) as items_per_pack,
    
    -- Combo/Multipack info
    combo_pack_raw as combo_pattern,
    toInt32OrNull(combo_multiplier) as combo_size,
    
    -- Flavor/Variant
    trim(coalesce(flavor_raw, scent_raw)) as flavor_variant,
    variant_feature,
    
    -- Tổng số lượng đơn vị trong pack
    COALESCE(toInt32OrNull(combo_multiplier), 1) as total_units_in_pack,
    
    -- SKU Key (normalized) cho grouping
    lower(
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                concat(
                    replace(replace(trim(REGEXP_REPLACE(product_family_dirty, '\\s+', ' ')), ' ', '_'), '-', '_'),
                    '_',
                    COALESCE(toString(toFloat32OrNull(weight_volume_numeric)), ''),
                    COALESCE(
                        CASE 
                            WHEN weight_volume_unit IN ('G', 'GR', 'GRAM') THEN 'g'
                            WHEN weight_volume_unit IN ('KG') THEN 'kg'
                            WHEN weight_volume_unit IN ('ML') THEN 'ml'
                            WHEN weight_volume_unit IN ('L') THEN 'l'
                        END, ''
                    )
                ),
                '_+',
                '_'
            ),
            '_$',
            ''
        )
    ) as product_variant_key,
    
    -- Product Family Key (không có size)
    lower(
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                replace(replace(trim(REGEXP_REPLACE(product_family_dirty, '\\s+', ' ')), ' ', '_'), '-', '_'),
                '_+',
                '_'
            ),
            '_$',
            ''
        )
    ) as product_family_key

FROM product_parsed
WHERE product_name IS NOT NULL
ORDER BY product_family, size_normalized_ml_or_g
