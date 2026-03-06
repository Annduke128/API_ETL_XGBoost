-- ============================================
-- Sales Reports Tables
-- ============================================

-- Bảng báo cáo bán hàng chi tiết (từ file Excel BaoCaoBanHangTheoLoiNhuan)
-- Lưu trữ dữ liệu giao dịch chi tiết
CREATE TABLE IF NOT EXISTS sales_reports (
    id SERIAL PRIMARY KEY,
    ngay_bao_cao DATE NOT NULL,
    
    -- Thông tin giao dịch
    ma_giao_dich VARCHAR(50),
    thoi_gian_giao_dich TIMESTAMP,
    chi_nhanh VARCHAR(100),
    
    -- Thông tin sản phẩm
    ma_hang VARCHAR(50),
    ma_vach VARCHAR(100),
    ten_hang VARCHAR(500),
    thuong_hieu VARCHAR(100),
    nhom_hang_cap_1 VARCHAR(200),
    nhom_hang_cap_2 VARCHAR(200),
    nhom_hang_cap_3 VARCHAR(200),
    
    -- Số liệu bán hàng
    sl_ban NUMERIC(15,2) DEFAULT 0,
    gia_ban_sp NUMERIC(15,2) DEFAULT 0,
    gia_von_sp NUMERIC(15,2) DEFAULT 0,
    loi_nhuan_sp NUMERIC(15,2) DEFAULT 0,
    
    -- Tổng hợp theo giao dịch
    tong_tien_hang NUMERIC(15,2) DEFAULT 0,
    giam_gia NUMERIC(15,2) DEFAULT 0,
    doanh_thu NUMERIC(15,2) DEFAULT 0,
    tong_gia_von NUMERIC(15,2) DEFAULT 0,
    loi_nhuan_gop NUMERIC(15,2) DEFAULT 0,
    
    -- Metadata
    source_file VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales_reports(ngay_bao_cao);
CREATE INDEX IF NOT EXISTS idx_sales_product ON sales_reports(ma_hang);
CREATE INDEX IF NOT EXISTS idx_sales_barcode ON sales_reports(ma_vach);
CREATE INDEX IF NOT EXISTS idx_sales_branch ON sales_reports(chi_nhanh);
CREATE INDEX IF NOT EXISTS idx_sales_transaction ON sales_reports(ma_giao_dich);

-- View kết hợp sales với products
CREATE OR REPLACE VIEW v_sales_with_products AS
SELECT s.*, 
       p.thuong_hieu as product_brand, 
       p.nhom_hang_cap_1 as product_cat1, 
       p.nhom_hang_cap_2 as product_cat2, 
       p.nhom_hang_cap_3 as product_cat3,
       CASE WHEN p.id IS NOT NULL THEN true ELSE false END as co_trong_products
FROM sales_reports s
LEFT JOIN products p ON s.ma_vach = p.ma_vach OR s.ma_hang = p.ma_hang;

-- Comment
COMMENT ON TABLE sales_reports IS 'Báo cáo bán hàng chi tiết import từ Excel';
COMMENT ON VIEW v_sales_with_products IS 'View bán hàng kết hợp thông tin sản phẩm';
