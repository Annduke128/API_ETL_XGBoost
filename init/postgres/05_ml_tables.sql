-- ML Tables for Forecasting and Predictions
-- Tạo bảng lưu kết quả dự báo từ ML models

-- Bảng lưu kết quả dự báo
DROP TABLE IF EXISTS ml_forecasts CASCADE;

CREATE TABLE ml_forecasts (
    id SERIAL PRIMARY KEY,
    forecast_date DATE NOT NULL,
    chi_nhanh VARCHAR(100),
    ma_hang VARCHAR(50),
    ten_san_pham VARCHAR(500),
    nhom_hang_cap_1 VARCHAR(200),
    nhom_hang_cap_2 VARCHAR(200),
    abc_class VARCHAR(10),
    predicted_quantity FLOAT,
    predicted_quantity_raw FLOAT,
    predicted_revenue DECIMAL(15,2),
    predicted_profit_margin FLOAT,
    confidence_lower FLOAT,
    confidence_upper FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes cho truy vấn nhanh
CREATE INDEX idx_forecasts_date ON ml_forecasts(forecast_date);
CREATE INDEX idx_forecasts_product ON ml_forecasts(ma_hang);
CREATE INDEX idx_forecasts_abc ON ml_forecasts(abc_class);

-- Bảng lưu model metrics
DROP TABLE IF EXISTS ml_model_metrics CASCADE;

CREATE TABLE ml_model_metrics (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    training_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    best_mape FLOAT,
    n_trials INTEGER,
    best_params TEXT,
    feature_importance TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_model_metrics_name ON ml_model_metrics(model_name);
CREATE INDEX idx_model_metrics_date ON ml_model_metrics(training_date);

COMMENT ON TABLE ml_forecasts IS 'Lưu kết quả dự báo từ ML models';
COMMENT ON TABLE ml_model_metrics IS 'Lưu metrics của các ML models';
