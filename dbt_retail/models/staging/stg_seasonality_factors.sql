{{
    config(
        materialized='view',
        tags=['staging', 'reference']
    )
}}

-- Seasonality factors as ephemeral model instead of seed
-- Due to ClickHouse seed issues

SELECT 
    1 AS month,
    'Winter' AS season,
    'Tet Nguyen Dan' AS peak_reason
UNION ALL SELECT 2, 'Winter', 'Sau Tet'
UNION ALL SELECT 3, 'Spring', 'Mua xuan'
UNION ALL SELECT 4, 'Spring', 'Gio To'
UNION ALL SELECT 5, 'Spring', 'Mua cuoi'
UNION ALL SELECT 6, 'Summer', 'Mua he'
UNION ALL SELECT 7, 'Summer', 'Cao diem he'
UNION ALL SELECT 8, 'Summer', 'Back to school'
UNION ALL SELECT 9, 'Autumn', 'Thu sang'
UNION ALL SELECT 10, 'Autumn', 'Cuoi nam'
UNION ALL SELECT 11, 'Autumn', 'Black Friday'
UNION ALL SELECT 12, 'Winter', 'Giang sinh va nam moi'
