{{
    config(
        materialized='table',
        unique_key='ma_hang'
    )
}}

-- Transform dữ liệu từ seed product.csv sang chuẩn database
WITH source AS (
    SELECT 
        -- Mapping cột từ CSV sang database
        "Mã hàng" AS ma_hang,
        "Mã vạch" AS ma_vach,
        "Tên hàng" AS ten_hang,
        "Thương hiệu" AS thuong_hieu,
        -- Parse nhóm hàng 3 cấp (dùng >> làm delimiter)
        SPLIT_PART("Nhóm hàng(3 Cấp)", '>>', 1) AS nhom_hang_cap_1,
        SPLIT_PART("Nhóm hàng(3 Cấp)", '>>', 2) AS nhom_hang_cap_2,
        SPLIT_PART("Nhóm hàng(3 Cấp)", '>>', 3) AS nhom_hang_cap_3,
        -- Xử lý giá (chuyển sang text rồi loại bỏ dấu phẩy)
        CAST(REPLACE("Giá vốn"::TEXT, ',', '') AS DECIMAL(15,2)) AS gia_von_mac_dinh,
        CAST(REPLACE("Giá bán"::TEXT, ',', '') AS DECIMAL(15,2)) AS gia_ban_mac_dinh,
        -- Lọc chỉ lấy hàng hóa đang kinh doanh
        "Đang kinh doanh" AS dang_kinh_doanh
    FROM {{ ref('product') }}
    WHERE "Loại hàng" = 'Hàng hóa'
      AND "Mã hàng" IS NOT NULL 
      AND "Mã hàng" != ''
)

SELECT 
    ma_hang,
    ma_vach,
    ten_hang,
    thuong_hieu,
    NULLIF(TRIM(nhom_hang_cap_1), '') AS nhom_hang_cap_1,
    NULLIF(TRIM(nhom_hang_cap_2), '') AS nhom_hang_cap_2,
    NULLIF(TRIM(nhom_hang_cap_3), '') AS nhom_hang_cap_3,
    COALESCE(gia_von_mac_dinh, 0) AS gia_von_mac_dinh,
    COALESCE(gia_ban_mac_dinh, 0) AS gia_ban_mac_dinh,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM source
WHERE ma_hang IS NOT NULL
