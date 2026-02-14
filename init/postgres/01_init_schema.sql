-- Khởi tạo schema cho PostgreSQL

-- Bảng chi nhánh
CREATE TABLE IF NOT EXISTS branches (
    id SERIAL PRIMARY KEY,
    ma_chi_nhanh VARCHAR(50) UNIQUE NOT NULL,
    ten_chi_nhanh VARCHAR(255),
    dia_chi TEXT,
    thanh_pho VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bảng danh mục hàng hóa
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    ma_hang VARCHAR(50) UNIQUE NOT NULL,
    ma_vach VARCHAR(100),
    ten_hang VARCHAR(500),
    thuong_hieu VARCHAR(200),
    nhom_hang_cap_1 VARCHAR(200),
    nhom_hang_cap_2 VARCHAR(200),
    nhom_hang_cap_3 VARCHAR(200),
    gia_von_mac_dinh DECIMAL(15,2),
    gia_ban_mac_dinh DECIMAL(15,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bảng giao dịch (transactions)
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    ma_giao_dich VARCHAR(100) NOT NULL,
    chi_nhanh_id INTEGER REFERENCES branches(id),
    thoi_gian TIMESTAMP NOT NULL,
    tong_tien_hang DECIMAL(15,2),
    giam_gia DECIMAL(15,2),
    doanh_thu DECIMAL(15,2),
    tong_gia_von DECIMAL(15,2),
    loi_nhuan_gop DECIMAL(15,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ma_giao_dich, thoi_gian)
);

-- Bảng chi tiết giao dịch
CREATE TABLE IF NOT EXISTS transaction_details (
    id SERIAL PRIMARY KEY,
    giao_dich_id INTEGER REFERENCES transactions(id),
    product_id INTEGER REFERENCES products(id),
    so_luong INTEGER NOT NULL,
    gia_ban DECIMAL(15,2),
    gia_von DECIMAL(15,2),
    loi_nhuan DECIMAL(15,2),
    tong_loi_nhuan DECIMAL(15,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index cho performance
CREATE INDEX IF NOT EXISTS idx_transactions_time ON transactions(thoi_gian);
CREATE INDEX IF NOT EXISTS idx_transactions_branch ON transactions(chi_nhanh_id);
CREATE INDEX IF NOT EXISTS idx_transactions_ma_gd ON transactions(ma_giao_dich);
CREATE INDEX IF NOT EXISTS idx_transaction_details_product ON transaction_details(product_id);
CREATE INDEX IF NOT EXISTS idx_products_ma_hang ON products(ma_hang);

-- Bảng dự báo ML
CREATE TABLE IF NOT EXISTS ml_forecasts (
    id SERIAL PRIMARY KEY,
    forecast_date DATE NOT NULL,
    chi_nhanh VARCHAR(100),
    ma_hang VARCHAR(50),
    nhom_hang_cap_1 VARCHAR(200),
    predicted_quantity FLOAT,
    predicted_revenue DECIMAL(15,2),
    confidence_lower FLOAT,
    confidence_upper FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_forecasts_date ON ml_forecasts(forecast_date);
CREATE INDEX IF NOT EXISTS idx_forecasts_product ON ml_forecasts(ma_hang);


