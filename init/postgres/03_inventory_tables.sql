-- ============================================================================
-- INVENTORY TABLES - Bảng tồn kho và xuất nhập
-- Join với products qua ma_vach (barcode)
-- ============================================================================

-- Bảng dữ liệu tồn kho/xuất nhập từ file Excel
CREATE TABLE IF NOT EXISTS inventory_transactions (
    id SERIAL PRIMARY KEY,
    -- Thờigian
    ngay_bao_cao DATE NOT NULL,           -- Ngày báo cáo (từ tên file hoặc cột ngày)
    week_year VARCHAR(10),                -- Format: YYYY-WW
    
    -- Thông tin sản phẩm (từ file Excel)
    nhom_hang VARCHAR(255),               -- Nhóm hàng
    ma_hang VARCHAR(50),                  -- Mã hàng
    ma_vach VARCHAR(100) NOT NULL,        -- Mã vạch (dùng để JOIN với products)
    ten_hang VARCHAR(500),                -- Tên hàng
    thuong_hieu VARCHAR(200),             -- Thương hiệu
    don_vi_tinh VARCHAR(50),              -- Đơn vị tính
    
    -- Chi nhánh
    chi_nhanh VARCHAR(100) NOT NULL,
    
    -- Tồn kho
    ton_dau_ky INTEGER DEFAULT 0,
    gia_tri_dau_ky DECIMAL(15,2) DEFAULT 0,
    
    -- Nhập
    sl_nhap INTEGER DEFAULT 0,
    gia_tri_nhap DECIMAL(15,2) DEFAULT 0,
    
    -- Xuất
    sl_xuat INTEGER DEFAULT 0,
    gia_tri_xuat DECIMAL(15,2) DEFAULT 0,
    
    -- Tồn cuối
    ton_cuoi_ky INTEGER DEFAULT 0,
    gia_tri_cuoi_ky DECIMAL(15,2) DEFAULT 0,
    
    -- Metadata
    source_file VARCHAR(255),             -- Tên file nguồn
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraint để tránh duplicate
    UNIQUE(ma_vach, chi_nhanh, ngay_bao_cao)
);

-- Index cho inventory transactions
CREATE INDEX IF NOT EXISTS idx_inv_trans_date ON inventory_transactions(ngay_bao_cao);
CREATE INDEX IF NOT EXISTS idx_inv_trans_barcode ON inventory_transactions(ma_vach);
CREATE INDEX IF NOT EXISTS idx_inv_trans_branch ON inventory_transactions(chi_nhanh);
CREATE INDEX IF NOT EXISTS idx_inv_trans_product ON inventory_transactions(ma_hang);

-- View join inventory với products qua ma_vach
CREATE OR REPLACE VIEW v_inventory_with_products AS
SELECT 
    i.*,
    p.id as product_id,
    p.nhom_hang_cap_1,
    p.nhom_hang_cap_2,
    p.nhom_hang_cap_3,
    p.gia_von_mac_dinh,
    p.gia_ban_mac_dinh,
    -- Tính toán thêm
    CASE 
        WHEN i.sl_xuat > 0 THEN 
            ROUND(i.ton_cuoi_ky::numeric / i.sl_xuat, 2)
        ELSE NULL 
    END as so_ngay_ton_kho,  -- Coverage days
    CASE
        WHEN i.ton_dau_ky > 0 THEN
            ROUND(((i.ton_cuoi_ky - i.ton_dau_ky)::numeric / i.ton_dau_ky) * 100, 2)
        ELSE NULL
    END as bien_dong_ton_kho_pct,
    -- Kiểm tra consistency
    CASE
        WHEN (i.ton_dau_ky + i.sl_nhap - i.sl_xuat) != i.ton_cuoi_ky THEN 'ERROR'
        ELSE 'OK'
    END as consistency_check
FROM inventory_transactions i
LEFT JOIN products p ON i.ma_vach = p.ma_vach;

-- Comment
COMMENT ON TABLE inventory_transactions IS 'Dữ liệu xuất nhập tồn kho từ file Excel';
COMMENT ON VIEW v_inventory_with_products IS 'View tồn kho join với bảng products qua mã vạch';
