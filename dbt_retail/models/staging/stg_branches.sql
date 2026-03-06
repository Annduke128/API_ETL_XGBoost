{{
    config(
        materialized='view'
    )
}}

-- Branches data - currently empty, using dummy data
-- Will use actual data when branches table is populated

SELECT 
    'BHS001' AS branch_id,
    'BHS001' AS branch_code,
    'BHS Đại Phúc' AS branch_name,
    'Đại Phúc' AS address,
    'Bình Dương' AS city,
    'Standard' AS branch_type,
    now() AS created_at

UNION ALL

SELECT 
    'BHS002' AS branch_id,
    'BHS002' AS branch_code,
    'BHS Thủ Dầu Một' AS branch_name,
    'Thủ Dầu Một' AS address,
    'Bình Dương' AS city,
    'Flagship' AS branch_type,
    now() AS created_at
