-- Khởi tạo schema cho ClickHouse - Phiên bản cập nhật
-- Bao gồm tất cả các bảng đang tồn tại trong production

-- ============================================
-- 1. STAGING TABLES (Raw data from CSV imports)
-- ============================================

-- Staging products
CREATE TABLE IF NOT EXISTS staging_products (
    id Int64,
    ma_hang String,
    ma_vach String,
    ten_hang String,
    thuong_hieu String,
    nhom_hang_cap_1 String,
    nhom_hang_cap_2 String,
    nhom_hang_cap_3 String,
    gia_von_mac_dinh Float64,
    gia_ban_mac_dinh Float64,
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (ma_hang)
SETTINGS index_granularity = 8192;

-- Staging transactions
CREATE TABLE IF NOT EXISTS staging_transactions (
    id Int64,
    ma_giao_dich String,
    chi_nhanh_id Int64,
    thoi_gian DateTime,
    tong_tien_hang Float64,
    giam_gia Float64,
    khach_phai_tra Float64,
    khach_dua Float64,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (thoi_gian, ma_giao_dich)
SETTINGS index_granularity = 8192;

-- Staging transaction details
CREATE TABLE IF NOT EXISTS staging_transaction_details (
    id Int64,
    giao_dich_id Int64,
    product_id Int64,
    so_luong Int64,
    gia_ban Float64,
    gia_von Float64,
    loi_nhuan Float64,
    tong_loi_nhuan Float64,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (giao_dich_id, product_id)
SETTINGS index_granularity = 8192;

-- Staging branches
CREATE TABLE IF NOT EXISTS staging_branches (
    id Int64,
    ma_chi_nhanh String,
    ten_chi_nhanh String,
    dia_chi String,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (ma_chi_nhanh)
SETTINGS index_granularity = 8192;

-- ============================================
-- 2. STAGING VIEWS
-- ============================================

CREATE OR REPLACE VIEW stg_products AS
SELECT * FROM staging_products;

CREATE OR REPLACE VIEW stg_transactions AS
SELECT * FROM staging_transactions;

CREATE OR REPLACE VIEW stg_transaction_details AS
SELECT * FROM staging_transaction_details;

CREATE OR REPLACE VIEW stg_branches AS
SELECT * FROM staging_branches;

-- ============================================
-- 3. FACT TABLES
-- ============================================

-- Fact transactions (raw transaction data)
CREATE TABLE IF NOT EXISTS fact_transactions (
    thoi_gian DateTime,
    ngay Date,
    ma_giao_dich String,
    chi_nhanh String,
    ma_hang String,
    ten_hang String,
    thuong_hieu String,
    nhom_hang_cap_1 String,
    nhom_hang_cap_2 String,
    nhom_hang_cap_3 String,
    cap_1 String,
    cap_2 String,
    cap_3 String,
    so_luong Float64,
    gia_ban Float64,
    gia_von Float64,
    loi_nhuan Float64,
    doanh_thu Float64,
    giam_gia Float64,
    tong_gia_von Float64,
    loi_nhuan_gop Float64,
    ty_suat_loi_nhuan Float64,
    etl_timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(ngay)
ORDER BY (ngay, chi_nhanh, ma_hang)
TTL ngay + INTERVAL 3 YEAR
SETTINGS index_granularity = 8192;

-- Fact daily sales (aggregated by day)
CREATE TABLE IF NOT EXISTS fct_daily_sales (
    transaction_date Date,
    date_key UInt32,
    product_code String,
    product_id Int64,
    branch_code String,
    branch_id Int64,
    transaction_count UInt64,
    quantity_sold Int64,
    gross_revenue Float64,
    cost_of_goods_sold Float64,
    gross_profit Float64,
    avg_selling_price Float64,
    avg_profit_per_unit Float64,
    profit_margin Float64,
    etl_timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(transaction_date)
ORDER BY (transaction_date, product_code, branch_code)
SETTINGS index_granularity = 8192;

-- Fact regular sales (baseline - excluding promotions)
CREATE TABLE IF NOT EXISTS fct_regular_sales (
    transaction_date Date,
    date_key UInt32,
    product_code String,
    product_id Int64,
    branch_code String,
    branch_id Int64,
    transaction_count UInt64,
    quantity_sold Int64,
    gross_revenue Float64,
    cost_of_goods_sold Float64,
    gross_profit Float64,
    avg_selling_price Float64,
    avg_profit_per_unit Float64,
    profit_margin Float64,
    etl_timestamp DateTime DEFAULT now(),
    is_promotional_sale UInt8 DEFAULT 0,
    sale_type String DEFAULT 'regular'
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(transaction_date)
ORDER BY (transaction_date, product_code, branch_code)
SETTINGS index_granularity = 8192;

-- Fact promotional sales (promotion only)
CREATE TABLE IF NOT EXISTS fct_promotional_sales (
    transaction_date Date,
    date_key UInt32,
    product_code String,
    product_id Int64,
    branch_code String,
    branch_id Int64,
    transaction_count UInt64,
    quantity_sold Int64,
    gross_revenue Float64,
    cost_of_goods_sold Float64,
    gross_profit Float64,
    avg_selling_price Float64,
    avg_profit_per_unit Float64,
    profit_margin Float64,
    etl_timestamp DateTime DEFAULT now(),
    promotion_category String DEFAULT '',
    promotion_subcategory String DEFAULT '',
    is_promotional_sale UInt8 DEFAULT 1,
    sale_type String DEFAULT 'promotional'
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(transaction_date)
ORDER BY (transaction_date, product_code, branch_code)
SETTINGS index_granularity = 8192;

-- Fact monthly sales
CREATE TABLE IF NOT EXISTS fct_monthly_sales (
    year_month String,
    month_start_date Date,
    product_id Int64,
    branch_id Int64,
    total_transactions UInt64,
    total_quantity Int64,
    total_gross_revenue Float64,
    total_cogs Float64,
    total_gross_profit Float64,
    avg_selling_price Float64,
    avg_profit_margin Float64,
    etl_timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY substring(year_month, 1, 4)
ORDER BY (year_month, product_id)
SETTINGS index_granularity = 8192;

-- Fact inventory forecast input
CREATE TABLE IF NOT EXISTS fct_inventory_forecast_input (
    product_code String,
    product_name String,
    brand String,
    category_l1 String,
    avg_daily_sales Float64,
    std_daily_sales Float64,
    max_daily_sales Int64,
    p95_daily_sales Float64,
    avg_daily_revenue Float64,
    total_revenue Float64,
    selling_days UInt64,
    first_sale Date,
    last_sale Date,
    sales_velocity Nullable(Float64),
    suggested_safety_stock Float64,
    suggested_reorder_point Float64,
    suggested_order_quantity Float64,
    velocity_class String,
    demand_pattern String,
    etl_timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (product_code)
SETTINGS index_granularity = 8192;

-- Fact RFM analysis
CREATE TABLE IF NOT EXISTS fct_rfm_analysis (
    customer_id String,
    recency_days Int64,
    frequency Int64,
    monetary_value Float64,
    r_score Int32,
    f_score Int32,
    m_score Int32,
    rfm_score Float64,
    segment String,
    last_purchase_date Date,
    total_orders Int64,
    total_quantity Int64,
    etl_timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (customer_id)
SETTINGS index_granularity = 8192;

-- ============================================
-- 3.5 CONFIGURATION TABLES (Store Types, etc.)
-- ============================================

-- Store Types - Phân loại cửa hàng cho Store RFM và ML
CREATE TABLE IF NOT EXISTS store_types (
    type_code String,
    type_code_2 String,
    type_name_vn String,
    type_name_en String,
    description String,
    typical_area_m2 String,
    target_customer String
) ENGINE = MergeTree()
ORDER BY (type_code)
SETTINGS index_granularity = 8192;

-- Insert default store types
INSERT INTO store_types VALUES
('KPDT', 'UP', 'Cửa hàng khu phố đô thị', 'Urban Street Store', 'Cửa hàng trên đường phố khu đông dân cư đô thị', '50-200', 'Khách đi bộ + xe máy'),
('KCC', 'AP', 'Cửa hàng khu chung cư', 'Apartment Complex Store', 'Cửa hàng trong hoặc gần khu chung cư căn hộ', '30-100', 'Cư dân chung cư'),
('KCN', 'IZ', 'Cửa hàng khu công nghiệp', 'Industrial Zone Store', 'Cửa hàng phục vụ công nhân trong/gần KCN', '80-300', 'Công nhân KCN'),
('CTT', 'TM', 'Cửa hàng chợ truyền thống', 'Traditional Market Store', 'Cửa hàng trong chợ truyền thống', '15-50', 'Ngườ i mua sắm chợ'),
('KVNT', 'RL', 'Cửa hàng khu vực nông thôn', 'Rural Area Store', 'Cửa hàng ở xã huyện vùng nông thôn', '40-150', 'Ngườ i dân địa phương');

-- ============================================
-- 4. DIMENSION TABLES
-- ============================================

-- Dim date - Cách tạo đúng để có đầy đủ ngày
CREATE TABLE IF NOT EXISTS dim_date (
    date_key UInt32,
    full_date Date,
    year UInt16,
    year_name String,
    quarter UInt8,
    quarter_name String,
    month UInt8,
    month_name String,
    week_of_year UInt8,
    day_of_month UInt8,
    day_of_week UInt8,
    day_name Nullable(String),
    is_weekend UInt8,
    is_first_day_of_month UInt8,
    is_last_day_of_month UInt8,
    fiscal_year Int32
) ENGINE = ReplacingMergeTree()
ORDER BY (date_key)
SETTINGS index_granularity = 8192;

-- Insert data cho dim_date (2020-01-01 đến 2030-12-31)
-- Chạy sau khi tạo bảng
INSERT INTO dim_date
SELECT
    toYYYYMMDD(date_day) AS date_key,
    date_day AS full_date,
    toYear(date_day) AS year,
    concat('Năm ', toString(toYear(date_day))) AS year_name,
    toQuarter(date_day) AS quarter,
    concat('Q', toString(toQuarter(date_day)), '-', toString(toYear(date_day))) AS quarter_name,
    toMonth(date_day) AS month,
    formatDateTime(date_day, '%m/%Y') AS month_name,
    toWeek(date_day) AS week_of_year,
    toDayOfMonth(date_day) AS day_of_month,
    toDayOfWeek(date_day) AS day_of_week,
    CASE toDayOfWeek(date_day)
        WHEN 7 THEN 'Chủ nhật'
        WHEN 1 THEN 'Thứ hai'
        WHEN 2 THEN 'Thứ ba'
        WHEN 3 THEN 'Thứ tư'
        WHEN 4 THEN 'Thứ năm'
        WHEN 5 THEN 'Thứ sáu'
        WHEN 6 THEN 'Thứ bảy'
    END AS day_name,
    toDayOfWeek(date_day) IN (6, 7) AS is_weekend,
    toDayOfMonth(date_day) = 1 AS is_first_day_of_month,
    date_day = toLastDayOfMonth(date_day) AS is_last_day_of_month,
    CASE 
        WHEN toMonth(date_day) >= 4 
        THEN toYear(date_day)
        ELSE toYear(date_day) - 1
    END AS fiscal_year
FROM (
    SELECT arrayJoin(range(toUInt32(toDate('2020-01-01')), toUInt32(toDate('2031-01-01')), 1)) as date_day_int,
           toDate(date_day_int) as date_day
)
WHERE date_day <= '2030-12-31'
SETTINGS max_execution_time = 60;

-- Dim product
CREATE TABLE IF NOT EXISTS dim_product (
    product_id Int64,
    product_code String,
    barcode String,
    product_name String,
    brand String,
    category_level_1 String,
    category_level_2 String,
    category_level_3 String,
    default_cost_price Float64,
    default_selling_price Float64,
    default_margin_rate Float64,
    price_tier String,
    abc_class String DEFAULT 'C',
    total_historical_revenue Float64 DEFAULT 0,
    total_historical_quantity Int64 DEFAULT 0,
    historical_profit_margin Float64 DEFAULT 0,
    product_status String DEFAULT 'active',
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (product_code)
SETTINGS index_granularity = 8192;

-- Dim branch
CREATE TABLE IF NOT EXISTS dim_branch (
    branch_id Int64,
    branch_code String,
    branch_name String,
    address String,
    region String,
    branch_type String,
    is_active UInt8 DEFAULT 1,
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (branch_id)
SETTINGS index_granularity = 8192;

-- ============================================
-- 5. INTERMEDIATE VIEWS
-- ============================================

CREATE OR REPLACE VIEW int_inventory_movement AS
SELECT 
    f.product_code,
    p.product_name,
    p.brand,
    p.category_level_1,
    f.transaction_date,
    f.quantity_sold,
    f.gross_revenue,
    f.gross_profit
FROM fct_daily_sales f
LEFT JOIN dim_product p ON f.product_code = p.product_code;

CREATE OR REPLACE VIEW int_product_performance AS
SELECT 
    product_code,
    product_name,
    brand,
    category_level_1,
    category_level_2,
    abc_class,
    total_historical_revenue,
    total_historical_quantity,
    historical_profit_margin
FROM dim_product;

-- ============================================
-- 6. REPORT TABLES
-- ============================================

CREATE TABLE IF NOT EXISTS rpt_sales_kpi (
    period String,
    revenue Float64,
    profit Float64,
    quantity Int64,
    transactions UInt64,
    avg_margin Float64,
    avg_transaction_value Float64,
    avg_unit_price Float64,
    report_timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (period)
SETTINGS index_granularity = 8192;

-- ============================================
-- 7. LEGACY TABLES (từ init cũ - để tương thích)
-- ============================================

-- Bảng tổng hợp theo ngày (AggregatingMergeTree)
CREATE TABLE IF NOT EXISTS agg_daily_sales (
    ngay Date,
    chi_nhanh String,
    nhom_hang_cap_1 String,
    nhom_hang_cap_2 String,
    tong_doanh_thu AggregateFunction(sum, Float64),
    tong_loi_nhuan AggregateFunction(sum, Float64),
    tong_so_luong AggregateFunction(sum, Int64),
    so_giao_dich AggregateFunction(count, UInt64),
    etl_timestamp DateTime DEFAULT now()
) ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(ngay)
ORDER BY (ngay, chi_nhanh, nhom_hang_cap_1, nhom_hang_cap_2);

-- View cho báo cáo nhanh
CREATE OR REPLACE VIEW v_daily_sales_summary AS
SELECT
    ngay,
    chi_nhanh,
    nhom_hang_cap_1,
    nhom_hang_cap_2,
    sumMerge(tong_doanh_thu) as doanh_thu,
    sumMerge(tong_loi_nhuan) as loi_nhuan,
    sumMerge(tong_so_luong) as so_luong,
    countMerge(so_giao_dich) as so_giao_dich
FROM agg_daily_sales
GROUP BY ngay, chi_nhanh, nhom_hang_cap_1, nhom_hang_cap_2;
