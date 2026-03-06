-- ============================================================================
-- INVENTORY MANAGEMENT SCHEMA
-- Bảng quản lý tồn kho, nhập xuất hàng tuần
-- ============================================================================

-- Bảng tồn kho đầu kỳ/cuối kỳ theo tuần
CREATE TABLE IF NOT EXISTS inventory_weekly (
    id SERIAL PRIMARY KEY,
    week_year VARCHAR(10) NOT NULL,           -- Format: YYYY-WW (vd: 2024-10)
    ngay_bat_dau DATE NOT NULL,
    ngay_ket_thuc DATE NOT NULL,
    chi_nhanh VARCHAR(100) NOT NULL,
    ma_hang VARCHAR(50) NOT NULL,
    ton_dau_ky INTEGER DEFAULT 0,             -- Tồn đầu tuần
    nhap_trong_ky INTEGER DEFAULT 0,          -- Tổng nhập trong tuần
    xuat_trong_ky INTEGER DEFAULT 0,          -- Tổng xuất trong tuần
    ton_cuoi_ky INTEGER DEFAULT 0,            -- Tồn cuối tuần (tính toán hoặc từ file)
    gia_von_trung_binh DECIMAL(15,2),         -- Giá vốn TB (optional)
    gia_tri_ton_kho DECIMAL(15,2),            -- Giá trị tồn kho = ton_cuoi_ky * gia_von
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(week_year, chi_nhanh, ma_hang)
);

-- Index cho inventory queries
CREATE INDEX IF NOT EXISTS idx_inventory_week ON inventory_weekly(week_year);
CREATE INDEX IF NOT EXISTS idx_inventory_branch ON inventory_weekly(chi_nhanh);
CREATE INDEX IF NOT EXISTS idx_inventory_product ON inventory_weekly(ma_hang);
CREATE INDEX IF NOT EXISTS idx_inventory_date ON inventory_weekly(ngay_ket_thuc);

-- Bảng chi tiết phiếu nhập kho
CREATE TABLE IF NOT EXISTS inventory_receipts (
    id SERIAL PRIMARY KEY,
    ma_phieu VARCHAR(100) NOT NULL,
    ngay_nhap DATE NOT NULL,
    chi_nhanh VARCHAR(100) NOT NULL,
    ma_hang VARCHAR(50) NOT NULL,
    so_luong_nhap INTEGER NOT NULL,
    don_gia_nhap DECIMAL(15,2),
    thanh_tien DECIMAL(15,2),
    nha_cung_cap VARCHAR(200),
    ghi_chu TEXT,
    week_year VARCHAR(10),                    -- Reference đến inventory_weekly
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ma_phieu, ma_hang)
);

CREATE INDEX IF NOT EXISTS idx_receipts_week ON inventory_receipts(week_year);
CREATE INDEX IF NOT EXISTS idx_receipts_date ON inventory_receipts(ngay_nhap);

-- Bảng chi tiết phiếu xuất kho (bán hàng từ kho)
CREATE TABLE IF NOT EXISTS inventory_issues (
    id SERIAL PRIMARY KEY,
    ma_phieu VARCHAR(100) NOT NULL,
    ngay_xuat DATE NOT NULL,
    chi_nhanh VARCHAR(100) NOT NULL,
    ma_hang VARCHAR(50) NOT NULL,
    so_luong_xuat INTEGER NOT NULL,
    ly_do_xuat VARCHAR(50),                   -- 'Bán hàng', 'Hủy', 'Trả hàng NCC'
    ma_giao_dich VARCHAR(100),                -- Link đến transactions nếu là bán hàng
    week_year VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ma_phieu, ma_hang)
);

CREATE INDEX IF NOT EXISTS idx_issues_week ON inventory_issues(week_year);
CREATE INDEX IF NOT EXISTS idx_issues_date ON inventory_issues(ngay_xuat);

-- View tổng hợp tồn kho cho báo cáo
CREATE OR REPLACE VIEW v_inventory_summary AS
SELECT 
    i.week_year,
    i.chi_nhanh,
    i.ma_hang,
    p.ten_hang,
    p.nhom_hang_cap_1,
    p.nhom_hang_cap_2,
    p.nhom_hang_cap_3,
    i.ton_dau_ky,
    i.nhap_trong_ky,
    i.xuat_trong_ky,
    i.ton_cuoi_ky,
    i.gia_tri_ton_kho,
    -- Tính toán thêm
    CASE 
        WHEN i.xuat_trong_ky > 0 THEN 
            ROUND(i.ton_cuoi_ky::numeric / i.xuat_trong_ky, 2)
        ELSE NULL 
    END as so_ngay_ton_kho,                   -- Số ngày hàng tồn (coverage)
    CASE
        WHEN i.ton_dau_ky > 0 THEN
            ROUND(((i.ton_cuoi_ky - i.ton_dau_ky)::numeric / i.ton_dau_ky) * 100, 2)
        ELSE NULL
    END as tang_truong_ton_kho_pct
FROM inventory_weekly i
LEFT JOIN products p ON i.ma_hang = p.ma_hang;

COMMENT ON TABLE inventory_weekly IS 'Tồn kho tổng hợp theo tuần';
COMMENT ON TABLE inventory_receipts IS 'Chi tiết phiếu nhập kho';
COMMENT ON TABLE inventory_issues IS 'Chi tiết phiếu xuất kho';
