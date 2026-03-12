{{
    config(
        materialized='view',
        tags=['staging', 'reference', 'peak_days']
    )
}}

-- Peak days with impact levels
-- Level 1: 1 day impact
-- Level 2: 7 days impact (1 week)
-- Level 3: 14 days impact (2 weeks)

SELECT 1 AS month, 1 AS day, 'Tet Nguyen Dan' AS peak_reason, 3 AS peak_level, 14 AS impact_days
UNION ALL SELECT 1, 2, 'Tet Nguyen Dan', 3, 14
UNION ALL SELECT 1, 3, 'Tet Nguyen Dan', 3, 14
UNION ALL SELECT 2, 14, 'Valentine', 1, 1
UNION ALL SELECT 3, 8, 'Quoc te Nu', 1, 1
UNION ALL SELECT 4, 30, 'Gio To', 2, 7
UNION ALL SELECT 5, 1, 'Quoc te Lao dong', 2, 7
UNION ALL SELECT 6, 1, 'Quoc te Thieu nhi', 1, 1
UNION ALL SELECT 7, 1, 'Cao diem he', 2, 7
UNION ALL SELECT 8, 15, 'Back to school', 2, 7
UNION ALL SELECT 9, 2, 'Thu sang', 2, 7
UNION ALL SELECT 10, 20, 'Cuoi nam', 2, 7
UNION ALL SELECT 11, 11, 'Black Friday', 1, 1
UNION ALL SELECT 11, 29, 'Sale cuoi nam', 2, 7
UNION ALL SELECT 12, 24, 'Giang sinh', 2, 7
UNION ALL SELECT 12, 25, 'Giang sinh', 1, 1
UNION ALL SELECT 12, 31, 'Countdown', 1, 1
