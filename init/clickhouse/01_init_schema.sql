-- Khởi tạo schema cho ClickHouse

-- Bảng facts - giao dịch chi tiết
CREATE TABLE IF NOT EXISTS fact_transactions (
    thoi_gian DateTime,
    ngay Date,
    thang UInt16,
    nam UInt16,
    tuan UInt8,
    gio UInt8,
    thu_trong_tuan String,
    
    ma_giao_dich String,
    chi_nhanh String,
    ma_hang String,
    ma_vach String,
    ten_hang String,
    thuong_hieu String,
    nhom_hang_cap_1 String,
    nhom_hang_cap_2 String,
    nhom_hang_cap_3 String,
    
    so_luong Int32,
    gia_ban Decimal(15,2),
    gia_von Decimal(15,2),
    loi_nhuan_sp Decimal(15,2),
    
    tong_tien_hang Decimal(15,2),
    giam_gia Decimal(15,2),
    doanh_thu Decimal(15,2),
    tong_gia_von Decimal(15,2),
    loi_nhuan_gop Decimal(15,2),
    tong_loi_nhuan_hang_hoa Decimal(15,2),
    ty_suat_loi_nhuan Float64,
    
    etl_timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(thoi_gian)
ORDER BY (thoi_gian, chi_nhanh, ma_hang)
TTL thoi_gian + INTERVAL 3 YEAR
SETTINGS index_granularity = 8192;

-- Bảng tổng hợp theo ngày (AggregatingMergeTree)
CREATE TABLE IF NOT EXISTS agg_daily_sales (
    ngay Date,
    chi_nhanh String,
    nhom_hang_cap_1 String,
    nhom_hang_cap_2 String,
    
    tong_doanh_thu AggregateFunction(sum, Decimal(15,2)),
    tong_loi_nhuan AggregateFunction(sum, Decimal(15,2)),
    tong_so_luong AggregateFunction(sum, Int32),
    so_giao_dich AggregateFunction(count, UInt64),
    etl_timestamp DateTime DEFAULT now()
) ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(ngay)
ORDER BY (ngay, chi_nhanh, nhom_hang_cap_1, nhom_hang_cap_2);

-- Materialized View cho tổng hợp
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_sales
TO agg_daily_sales
AS
SELECT
    ngay,
    chi_nhanh,
    nhom_hang_cap_1,
    nhom_hang_cap_2,
    sumState(doanh_thu) as tong_doanh_thu,
    sumState(loi_nhuan_gop) as tong_loi_nhuan,
    sumState(so_luong) as tong_so_luong,
    countState() as so_giao_dich
FROM fact_transactions
GROUP BY ngay, chi_nhanh, nhom_hang_cap_1, nhom_hang_cap_2;

-- View cho báo cáo nhanh
CREATE VIEW IF NOT EXISTS v_daily_sales_summary AS
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
