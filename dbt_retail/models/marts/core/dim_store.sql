{{
  config(
    materialized = 'table',
    engine = 'ReplacingMergeTree(updated_at)',
    order_by = ['store_id'],
    unique_key = ['store_id'],
    tags = ['core', 'daily']
  )
}}

/*
    Dimension table: Cửa hàng (Stores)
    
    Join với store_types (bảng config trong ClickHouse) để lấy thông tin chi tiết:
    - store_type_name: Tên loại cửa hàng tiếng Việt
    - peer_group: Mã 2 ký tự (UP, AP, IZ, TM, RL) cho phân tích RFM
    
    5 loại cửa hàng:
    - KPDT: Khu Phố Đô Thị (UP - Urban)
    - KCC: Khu Chung Cư (AP - Apartment)
    - KCN: Khu Công Nghiệp (IZ - Industrial Zone)
    - CTT: Chợ Truyền Thống (TM - Traditional Market)
    - KVNT: Khu Vực Nông Thôn (RL - Rural)
*/

WITH store_base AS (
    SELECT 
        id as store_id_raw,
        ma_chi_nhanh as branch_code,
        ten_chi_nhanh as branch_name,
        dia_chi as address,
        thanh_pho as city
    FROM {{ source('retail_source', 'staging_branches') }}
),

store_typed AS (
    SELECT 
        *,
        'KPDT' as store_type_code,
        concat('KPDT_', 
            LPAD(toString(ROW_NUMBER() OVER (ORDER BY store_id_raw)), 3, '0')
        ) as store_id
    FROM store_base
),

store_enriched AS (
    SELECT 
        s.store_id,
        s.store_type_code,
        st.type_name_vn as store_type_name,
        st.type_code_2 as peer_group,
        st.description as store_type_description,
        st.typical_area_m2,
        st.target_customer,
        s.branch_code,
        s.branch_name as store_name,
        s.address,
        s.city,
        
        -- Default values cho các cột khác
        -- TODO: Cập nhật khi có dữ liệu thực tế
        NULL as store_area_m2,
        NULL as selling_area_m2,
        NULL as storage_area_m2,
        NULL as open_date,
        'active' as status,
        
        now() as created_at,
        now() as updated_at
    FROM store_typed s
    LEFT JOIN {{ source('retail_dw', 'store_types') }} st 
        ON s.store_type_code = st.type_code
)

SELECT * FROM store_enriched
ORDER BY store_id
