# 📊 Data Column Specification - Retail Analytics

> **Tài liệu này liệt kê tất cả các bảng và cột đang hoạt động trong hệ thống**
> **Cập nhật:** 2026-03-06  
> **Trạng thái:** ✅ 169 ngày DAILY DATA - PySpark ETL hoàn thành

---

## 🎯 Tổng quan

| Layer | Số bảng | Mô tả |
|-------|---------|-------|
| PostgreSQL (Source) | 5 | Dữ liệu gốc từ Excel imports |
| ClickHouse Staging | 4 | Raw data + Inventory cho ML |
| DBT Staging | 4 | Views xử lý cơ bản |
| Intermediate | 4 | Models trung gian (ephemeral/views) |
| Dimensions | 4 | Dimension tables |
| Facts | 6 | Fact tables cho ML & báo cáo |
| Reports | 1 | KPI reports |

**📊 Dữ liệu hiện có:**
- **169 ngày** daily data (2025-09-11 → 2026-03-06)
- **14,085 records** trong `fct_regular_sales`
- **7,197 peak days** với seasonal factors

---

## 🔥 PYSPARK ETL PIPELINE

### Data Flow

```
Excel Files (3 loại)
    ├── DanhSachSanPham_*.xlsx ──→ import_products_spark.py ──→ PostgreSQL only
    ├── BaoCaoXuatNhapTon_*.xlsx ─→ import_inventory_spark.py ─→ PostgreSQL + ClickHouse ⭐
    └── BaoCaoBanHang_*.xlsx ────→ import_sales_spark.py ──────→ PostgreSQL ──→ dbt ──→ ClickHouse
                                          ↓ (Lấy datetime từ cột "Thởi gian (theo giao dịch)")
                                    169 ngày daily data
```

### Lý do thiết kế

| Loại dữ liệu | PostgreSQL | ClickHouse | Lý do |
|-------------|------------|------------|-------|
| **Products** | ✅ | ❌ | Chỉ dùng để tham chiếu, không cần ML |
| **Inventory** | ✅ | ✅ **Trực tiếp** | Cần `ton_cuoi_ky` cho ML tính toán tồn kho tối ưu |
| **Sales** | ✅ | ✅ Via dbt | Qua dbt transform rồi mới vào ClickHouse |

---

## 📋 Chi tiết các bảng và cột

### 1. SOURCE TABLES (PostgreSQL)

#### `ml_forecasts` (Dự báo ML) ⭐ **NEW**
Lưu kết quả dự báo từ XGBoost models

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| id | SERIAL PK | ID tự động |
| forecast_date | DATE | Ngày dự báo |
| chi_nhanh | VARCHAR(100) | Chi nhánh |
| ma_hang | VARCHAR(50) | Mã hàng |
| ten_san_pham | VARCHAR(500) | Tên sản phẩm |
| nhom_hang_cap_1 | VARCHAR(200) | Nhóm hàng cấp 1 |
| nhom_hang_cap_2 | VARCHAR(200) | Nhóm hàng cấp 2 |
| abc_class | VARCHAR(10) | Phân loại ABC (A/B/C) |
| predicted_quantity | FLOAT | Số lượng dự báo (adjusted) |
| predicted_quantity_raw | FLOAT | Số lượng dự báo (raw từ model) |
| predicted_revenue | DECIMAL(15,2) | Doanh thu dự báo |
| predicted_profit_margin | FLOAT | Biên lợi nhuận dự báo |
| confidence_lower | FLOAT | Ngưỡng tin cậy dưới (95% CI) |
| confidence_upper | FLOAT | Ngưỡng tin cậy trên (95% CI) |
| created_at | TIMESTAMP | Thởi gian tạo |

**Indexes:**
- `idx_forecasts_date` ON forecast_date
- `idx_forecasts_product` ON ma_hang
- `idx_forecasts_abc` ON abc_class

#### `ml_model_metrics` (Metrics Model) ⭐ **NEW**
Lưu metrics và thông tin training của các ML models

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| id | SERIAL PK | ID tự động |
| model_name | VARCHAR(100) | Tên model (product_quantity, category_trend) |
| training_date | TIMESTAMP | Ngày training |
| best_mape | FLOAT | Mean Absolute Percentage Error tốt nhất |
| n_trials | INTEGER | Số lần thử nghiệm (Optuna trials) |
| best_params | TEXT | Parameters tốt nhất (JSON format) |
| feature_importance | TEXT | Feature importance (JSON format) |
| created_at | TIMESTAMP | Thởi gian tạo |

**Indexes:**
- `idx_model_metrics_name` ON model_name
- `idx_model_metrics_date` ON training_date

---

#### `products` (16,025 dòng)
Dữ liệu sản phẩm từ Excel DanhSachSanPham

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| id | Int64 | ID sản phẩm (PK) |
| ma_hang | String | Mã hàng (unique) |
| ma_vach | String | Mã vạch |
| ten_hang | String | Tên hàng |
| thuong_hieu | String | Thương hiệu |
| nhom_hang_cap_1 | String | Nhóm hàng cấp 1 |
| nhom_hang_cap_2 | String | Nhóm hàng cấp 2 |
| nhom_hang_cap_3 | String | Nhóm hàng cấp 3 |
| gia_von_mac_dinh | Decimal | Giá vốn mặc định |
| gia_ban_mac_dinh | Decimal | Giá bán mặc định |
| **ton_nho_nhat** | **Decimal** | **Tồn nhỏ nhất (min stock level)** | ⭐ **Mới** |
| created_at | DateTime | Thởi gian tạo |

#### `inventory_transactions` (1,765 dòng/tuần)
Dữ liệu tồn kho từ Excel BaoCaoXuatNhapTon - **QUAN TRỌNG CHO ML**

| Cột | Kiểu dữ liệu | Mô tả | ML Relevance |
|-----|--------------|-------|--------------|
| id | Int64 | ID tự động | |
| ngay_bao_cao | Date | Ngày báo cáo | ✅ Time series |
| week_year | String | Tuần-năm (YYYY-WW) | ✅ Grouping |
| ma_hang | String | Mã hàng | ✅ Product key |
| ma_vach | String | Mã vạch (unique per product) | ✅ Product key |
| ten_hang | String | Tên hàng | |
| nhom_hang | String | Nhóm hàng | ✅ Category |
| thuong_hieu | String | Thương hiệu | |
| don_vi_tinh | String | Đơn vị tính | |
| chi_nhanh | String | Chi nhánh | ✅ Branch key |
| **ton_dau_ky** | Int64 | Tồn đầu kỳ | ✅ Input |
| gia_tri_dau_ky | Float64 | Giá trị đầu kỳ | |
| sl_nhap | Int64 | Số lượng nhập | ✅ Input |
| gia_tri_nhap | Float64 | Giá trị nhập | |
| sl_xuat | Int64 | Số lượng xuất | ✅ Input |
| gia_tri_xuat | Float64 | Giá trị xuất | |
| **ton_cuoi_ky** | Int64 | **Tồn cuối kỳ = Tồn hiện tại** | ⭐ **QUAN TRỌNG NHẤT** |
| gia_tri_cuoi_ky | Float64 | Giá trị cuối kỳ | |
| source_file | String | File nguồn | |
| created_at | DateTime | Thởi gian tạo | |

**⚠️ Ghi chú ML:** `ton_cuoi_ky` là tồn kho thực tế cuối tuần, dùng để tính:
```
Lượng cần nhập = MAX(Dự báo nhu cầu tuần tới, Tồn kho tối thiểu) - ton_cuoi_ky
```

#### `transactions` (7,947 dòng)
Giao dịch từ Excel BaoCaoBanHang - **ĐÃ CÓ DAILY DATA**

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| id | Int64 | ID giao dịch (PK) |
| ma_giao_dich | String | Mã giao dịch |
| thoi_gian | DateTime | Thởi gian giao dịch đầy đủ (từ cột "Thởi gian (theo giao dịch)") |
| tong_tien_hang | Decimal | Tổng tiền hàng |
| giam_gia | Decimal | Giảm giá |
| doanh_thu | Decimal | Doanh thu |
| tong_gia_von | Decimal | Tổng giá vốn |
| loi_nhuan_gop | Decimal | Lợi nhuận gộp |
| created_at | DateTime | Thởi gian tạo |

**✅ Date range:** 2025-09-11 → 2026-03-06 (169 ngày)

#### `transaction_details` (17,262 dòng)
Chi tiết giao dịch

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| id | Int64 | ID chi tiết (PK) |
| giao_dich_id | Int64 | ID giao dịch (FK) |
| product_id | Int64 | ID sản phẩm (FK) |
| so_luong | Int64 | Số lượng |
| gia_ban | Decimal | Giá bán |
| gia_von | Decimal | Giá vốn |
| created_at | DateTime | Thởi gian tạo |

---

### 2. STAGING TABLES (ClickHouse)

#### `staging_products` (16,025 dòng)
Sync từ PostgreSQL qua dbt

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| id | Int64 | ID sản phẩm |
| ma_hang | String | Mã hàng |
| ma_vach | String | Mã vạch |
| ten_hang | String | Tên hàng |
| thuong_hieu | String | Thương hiệu |
| nhom_hang_cap_1 | String | Nhóm hàng cấp 1 |
| nhom_hang_cap_2 | String | Nhóm hàng cấp 2 |
| nhom_hang_cap_3 | String | Nhóm hàng cấp 3 |
| gia_von_mac_dinh | Float64 | Giá vốn mặc định |
| gia_ban_mac_dinh | Float64 | Giá bán mặc định |
| created_at | DateTime | Thởi gian tạo |
| updated_at | DateTime | Thởi gian cập nhật |

#### `staging_inventory_transactions` (1,765 dòng) ⭐ **ML INPUT**
Ghi trực tiếp từ PySpark ETL

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| id | Int64 | ID |
| ngay_bao_cao | String | Ngày báo cáo (YYYY-MM-DD) |
| week_year | String | Tuần-năm |
| nhom_hang | String | Nhóm hàng |
| ma_hang | String | Mã hàng |
| ma_vach | String | Mã vạch |
| ten_hang | String | Tên hàng |
| thuong_hieu | String | Thương hiệu |
| don_vi_tinh | String | Đơn vị tính |
| chi_nhanh | String | Chi nhánh |
| **ton_dau_ky** | Int64 | Tồn đầu kỳ |
| gia_tri_dau_ky | Float64 | Giá trị đầu kỳ |
| **sl_nhap** | Int64 | Số lượng nhập |
| gia_tri_nhap | Float64 | Giá trị nhập |
| **sl_xuat** | Int64 | Số lượng xuất |
| gia_tri_xuat | Float64 | Giá trị xuất |
| **ton_cuoi_ky** | Int64 | **Tồn cuối kỳ (tồn hiện tại)** |
| gia_tri_cuoi_ky | Float64 | Giá trị cuối kỳ |
| source_file | String | File nguồn |
| created_at | DateTime | Thởi gian tạo |
| updated_at | DateTime | Thởi gian cập nhật |

#### `staging_transactions` (7,947 dòng)
Sync từ PostgreSQL qua dbt - **169 ngày daily**

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| id | Int64 | ID giao dịch |
| ma_giao_dich | String | Mã giao dịch |
| chi_nhanh_id | String | ID chi nhánh |
| thoi_gian | DateTime | Thởi gian giao dịch |
| tong_tien_hang | Float64 | Tổng tiền hàng |
| giam_gia | Float64 | Giảm giá |
| doanh_thu | Float64 | Doanh thu |
| tong_gia_von | Float64 | Tổng giá vốn |
| loi_nhuan_gop | Float64 | Lợi nhuận gộp |
| created_at | DateTime | Thởi gian tạo |

#### `staging_transaction_details` (17,262 dòng)
Sync từ PostgreSQL qua dbt

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| id | Int64 | ID chi tiết |
| giao_dich_id | Int64 | ID giao dịch |
| product_id | Int64 | ID sản phẩm |
| so_luong | Int64 | Số lượng |
| gia_ban | Float64 | Giá bán |
| gia_von | Float64 | Giá vốn |
| loi_nhuan | String | Lợi nhuận (raw) |
| tong_loi_nhuan | String | Tổng lợi nhuận (raw) |
| created_at | DateTime | Thởi gian tạo |

---

### 3. DBT STAGING VIEWS

#### `stg_products` (16,025 dòng)
View sản phẩm đã làm sạch

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| product_id | Int64 | ID sản phẩm |
| product_code | String | Mã sản phẩm |
| barcode | String | Mã vạch |
| product_name | String | Tên sản phẩm |
| brand | String | Thương hiệu |
| category_level_1 | String | Danh mục cấp 1 |
| category_level_2 | String | Danh mục cấp 2 |
| category_level_3 | String | Danh mục cấp 3 |
| default_cost_price | Float64 | Giá vốn mặc định |
| default_selling_price | Float64 | Giá bán mặc định |
| default_margin_rate | Float64 | Tỷ lệ lợi nhuận |

#### `stg_transactions` (7,947 dòng)
View giao dịch đã làm sạch - **169 ngày**

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| transaction_id | Int64 | ID giao dịch |
| transaction_code | String | Mã giao dịch |
| branch_id | Int64 | ID chi nhánh |
| branch_code | Int64 | Mã chi nhánh |
| transaction_timestamp | DateTime | Thởi gian giao dịch |
| transaction_date | Date | Ngày giao dịch |
| gross_amount | Float64 | Tổng tiền hàng |
| discount_amount | Float64 | Giảm giá |
| revenue | Float64 | Doanh thu |
| total_cost | Float64 | Tổng giá vốn |
| gross_profit | Float64 | Lợi nhuận gộp |

#### `stg_transaction_details` (17,262 dòng)
View chi tiết giao dịch đã làm sạch

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| detail_id | Int64 | ID chi tiết |
| transaction_id | Int64 | ID giao dịch |
| product_id | Int64 | ID sản phẩm |
| product_code | String | Mã sản phẩm |
| product_name | String | Tên sản phẩm |
| brand | String | Thương hiệu |
| category_l1 | String | Danh mục cấp 1 |
| category_l2 | String | Danh mục cấp 2 |
| quantity | Int64 | Số lượng |
| unit_price | Float64 | Đơn giá |
| selling_price | Float64 | Giá bán |
| cost_price | Float64 | Giá vốn |
| line_revenue | Float64 | Doanh thu dòng |
| line_cost | Float64 | Chi phí dòng |
| line_profit | Float64 | Lợi nhuận dòng |

#### `stg_branches` (2 dòng)
View chi nhánh

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| branch_id | String | ID chi nhánh |
| branch_code | String | Mã chi nhánh |
| branch_name | String | Tên chi nhánh |
| address | String | Địa chỉ |
| city | String | Thành phố |
| branch_type | String | Loại chi nhánh |

---

### 4. DIMENSION TABLES

#### `dim_date` (4,018 dòng)
Bảng dimension ngày tháng

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| date_key | UInt32 | Key ngày (YYYYMMDD) |
| full_date | Date | Ngày đầy đủ |
| year | UInt16 | Năm |
| month | UInt8 | Tháng |
| day | UInt8 | Ngày |
| quarter | UInt8 | Quý |
| week_of_year | UInt8 | Tuần trong năm |
| day_of_week | UInt8 | Thứ trong tuần |
| day_name | String | Tên thứ |
| month_name | String | Tên tháng |
| is_weekend | UInt8 | Cuối tuần |
| is_month_start | UInt8 | Đầu tháng |
| is_month_end | UInt8 | Cuối tháng |
| fiscal_year | UInt16 | Năm tài chính |

#### `dim_product` (16,025 dòng)
Dimension sản phẩm

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| product_id | Int64 | ID sản phẩm |
| product_code | String | Mã sản phẩm |
| barcode | String | Mã vạch |
| product_name | String | Tên sản phẩm |
| clean_name | String | Tên đã làm sạch |
| brand | String | Thương hiệu |
| category_level_1 | String | Danh mục cấp 1 |
| category_level_2 | String | Danh mục cấp 2 |
| category_level_3 | String | Danh mục cấp 3 |
| packaging_type | String | Loại đóng gói |
| weight | Float64 | Trọng lượng |
| unit | String | Đơn vị |
| default_selling_price | Float64 | Giá bán mặc định |
| abc_class | String | Phân loại ABC |
| total_historical_revenue | Float64 | Tổng doanh thu lịch sử |
| total_historical_quantity | Float64 | Tổng số lượng lịch sử |

#### `dim_branch` (1 dòng)
Dimension chi nhánh

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| branch_id | String | ID chi nhánh |
| branch_code | String | Mã chi nhánh |
| branch_name | String | Tên chi nhánh |
| address | String | Địa chỉ |
| city | String | Thành phố |
| branch_type | String | Loại chi nhánh |
| total_historical_revenue | Float64 | Tổng doanh thu lịch sử |
| total_historical_transactions | Float64 | Tổng số giao dịch |
| performance_tier | String | Phân loại hiệu suất |

#### `dim_store` (2 dòng)
Dimension cửa hàng

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| store_id | String | ID cửa hàng |
| store_type_code | String | Mã loại cửa hàng |
| store_type_name | String | Tên loại cửa hàng |
| peer_group | String | Nhóm đối chiếu |
| branch_code | String | Mã chi nhánh |
| store_name | String | Tên cửa hàng |
| address | String | Địa chỉ |
| city | String | Thành phố |
| status | String | Trạng thái |

---

### 5. FACT TABLES

#### `fct_daily_sales` (14,085 dòng) ⭐ **Bảng chính cho ML - 169 ngày**
Doanh số hàng ngày

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| transaction_date | Date | Ngày giao dịch |
| date_key | UInt32 | Key ngày |
| product_code | String | Mã sản phẩm |
| product_id | Int64 | ID sản phẩm |
| branch_code | String | Mã chi nhánh |
| branch_id | String | ID chi nhánh |
| transaction_count | UInt64 | Số giao dịch |
| quantity_sold | Int64 | Số lượng bán |
| gross_revenue | Float64 | Doanh thu gộp |
| cost_of_goods_sold | Float64 | Giá vốn hàng bán |
| gross_profit | Float64 | Lợi nhuận gộp |
| avg_selling_price | Float64 | Giá bán trung bình |
| avg_profit_per_unit | Float64 | Lợi nhuận/đơn vị |
| profit_margin | Float64 | Biên lợi nhuận |

**📊 Stats:** 169 ngày, từ 2025-09-11 đến 2026-03-06

#### `fct_regular_sales` (14,085 dòng) ⭐ **ML Training - Baseline - 169 ngày**
Doanh số thường (không khuyến mại)

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| transaction_date | Date | Ngày giao dịch |
| product_code | String | Mã sản phẩm |
| quantity_sold | Int64 | Số lượng bán |
| gross_revenue | Float64 | Doanh thu gộp |
| gross_profit | Float64 | Lợi nhuận gộp |
| is_promotional_sale | Int8 | Flag khuyến mại (=0) |
| sale_type | String | Loại bán (= 'regular') |

#### `fct_promotional_sales` (23 dòng)
Doanh số khuyến mại

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| transaction_date | Date | Ngày giao dịch |
| product_code | String | Mã sản phẩm |
| quantity_sold | Int64 | Số lượng bán |
| gross_revenue | Float64 | Doanh thu gộp |
| promotion_category | String | Danh mục khuyến mại |
| is_promotional_sale | Int8 | Flag khuyến mại (=1) |

#### `fct_monthly_sales` (14,085 dòng)
Doanh số hàng tháng

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| year_month | String | Tháng (YYYY-MM) |
| product_code | String | Mã sản phẩm |
| quantity_sold | Int64 | Số lượng bán |
| gross_revenue | Float64 | Doanh thu gộp |

#### `fct_daily_sales_with_seasonal` (14,085 dòng)
Doanh số có thông tin seasonal - **169 ngày**

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| transaction_date | Date | Ngày giao dịch |
| product_code | String | Mã sản phẩm |
| gross_revenue | Float64 | Doanh thu |
| seasonal_factor | Float64 | Hệ số theo mùa |
| peak_reason | String | Lý do đỉnh điểm |
| is_peak_day | Int8 | Ngày đỉnh điểm |
| season | String | Mùa (Winter/Spring/Summer/Autumn) |

#### `fct_inventory_forecast_input` (1,472 dòng) ⭐ **INVENTORY ML**
Input cho dự báo tồn kho

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| product_code | String | Mã sản phẩm |
| transaction_date | Date | Ngày |
| units_sold | Int64 | Số lượng bán |
| revenue | Float64 | Doanh thu |
| stock_level | Int64 | Mức tồn kho |

---

### 6. INTERMEDIATE MODELS

#### `int_dynamic_seasonal_factor` ⭐ **PEAK DAYS VỚI LEVELS**
Tính toán dynamic seasonal factor với peak days và impact levels

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| month | UInt8 | Tháng |
| peak_reason | String | Lý do peak (Tet, Black Friday...) |
| **peak_level** | Int8 | **Mức độ peak (1, 2, 3)** |
| **impact_days** | Int16 | **Số ngày ảnh hưởng** |
| actual_avg_revenue | Float64 | Doanh thu TB thực tế trong impact range |
| baseline_revenue | Float64 | Doanh thu TB baseline |
| **revenue_factor** | Float64 | **Hệ số revenue** |
| **quantity_factor** | Float64 | **Hệ số quantity** |
| **seasonal_factor** | Float64 | **Hệ số seasonal tổng hợp** |
| num_peak_days | UInt64 | Số ngày peak trong data |
| baseline_day_type | String | Loại ngày baseline |
| **is_peak_day** | UInt8 | **Flag ngày peak (0/1)** |
| calculated_at | DateTime | Thởi gian tính toán |

**Peak Levels:**
- **Level 1**: 1 ngày impact (Valentine, Black Friday...)
- **Level 2**: 7 ngày impact (Gio To, Quoc te Lao dong...)
- **Level 3**: 14 ngày impact (Tet Nguyen Dan...)

#### `int_product_performance` (2,098 dòng)
Hiệu suất sản phẩm

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| product_code | String | Mã sản phẩm |
| total_revenue | Float64 | Tổng doanh thu |
| total_quantity_sold | Int64 | Tổng số lượng |
| profit_margin | Float64 | Biên lợi nhuận |
| abc_class | String | Phân loại ABC |
| last_sale_date | Date | Ngày bán gần nhất |

#### `int_product_abc_classification` (16,025 dòng)
Phân loại ABC

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| product_id | Int64 | ID sản phẩm |
| product_code | String | Mã sản phẩm |
| total_historical_revenue | Float64 | Tổng doanh thu |
| abc_class | String | A/B/C |
| revenue_percentile | Int64 | Phân vị doanh thu |

#### `int_inventory_movement` (14,085 dòng)
Chuyển động tồn kho

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| transaction_date | Date | Ngày |
| product_code | String | Mã sản phẩm |
| units_sold | Int64 | Số lượng bán |
| revenue | Float64 | Doanh thu |
| cogs | Float64 | Giá vốn |

#### `int_sales_daily` (14,085 dòng)
Tổng hợp doanh số hàng ngày

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| transaction_date | Date | Ngày giao dịch |
| product_id | Int64 | ID sản phẩm |
| product_code | String | Mã sản phẩm |
| branch_id | String | ID chi nhánh |
| branch_code | String | Mã chi nhánh |
| transaction_count | Int64 | Số giao dịch |
| quantity_sold | Int64 | Số lượng bán |
| gross_revenue | Float64 | Doanh thu gộp |
| cost_of_goods_sold | Float64 | Giá vốn hàng bán |
| gross_profit | Float64 | Lợi nhuận gộp |

---

### 7. REPORTS

#### `rpt_sales_kpi` (3 dòng)
Báo cáo KPI

| Cột | Kiểu dữ liệu | Mô tả |
|-----|--------------|-------|
| kpi_name | String | Tên KPI |
| kpi_value | Float64 | Giá trị |
| kpi_period | String | Kỳ |

---

## 🔗 Data Lineage

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           🔥 PYSPARK ETL PIPELINE (DAILY DATA)                           │
└─────────────────────────────────────────────────────────────────────────────────────────┘

Excel Files (3 loại)
    │
    ├── DanhSachSanPham_*.xlsx 
    │   └── import_products_spark.py ──→ PostgreSQL.products
    │
    ├── BaoCaoXuatNhapTon_*.xlsx 
    │   └── import_inventory_spark.py ─┬─→ PostgreSQL.inventory_transactions
    │                                  └─→ ClickHouse.staging_inventory_transactions
    │
    └── BaoCaoBanHang_*.xlsx 
        └── import_sales_spark.py ───────┬─→ PostgreSQL.transactions (169 ngày)
            (Lấy datetime từ cột        └─→ PostgreSQL.transaction_details
             "Thởi gian (theo giao dịch)")     ↓
                                           sync_to_clickhouse.py
                                                ↓
                                    ClickHouse.staging_transactions
                                                ↓
                                              dbt run
                                                ↓
                                    ┌──────────────────────────────┐
                                    │  fct_regular_sales (169 ngày)│
                                    │  fct_daily_sales (14K rows)  │
                                    │  int_dynamic_seasonal_factor │
                                    │    (peak_level, impact_days) │
                                    └──────────────────────────────┘
                                                ↓
                                       ML Pipeline (XGBoost)
```

---

## 🎯 Bảng chính cho ML

| Bảng | Mục đích | Số dòng | Ngày | Nguồn |
|------|----------|---------|------|-------|
| `fct_regular_sales` | Training baseline model | 14,085 | 169 | dbt transform |
| `fct_daily_sales_with_seasonal` | Training với seasonal | 14,085 | 169 | dbt transform |
| `fct_inventory_forecast_input` | Inventory forecasting | 1,472 | - | dbt transform |
| `staging_inventory_transactions` | **Tồn kho thực tế** | 1,765 | - | PySpark direct |
| `int_dynamic_seasonal_factor` | **Peak days + Levels** | 3 | - | dbt view |

---

## 🧮 Inventory Optimization Formula (Cập nhật)

Sử dụng `ton_cuoi_ky` từ `staging_inventory_transactions` và `ton_nho_nhat` từ `products`:

```python
# Công thức tính lượng cần nhập (Updated)
forecast_demand = ml_predict_next_week_demand(product_code)    # From XGBoost (7 days)
min_stock_level = products.ton_nho_nhat                         # Tồn nhỏ nhất từ DanhSachSanPham
current_stock = inventory_transactions.ton_cuoi_ky             # Tồn hiện tại

# Lượng cần nhập = MAX(Dự báo, Tồn nhỏ nhất) - Tồn hiện tại
required_purchase = max(forecast_demand, min_stock_level) - current_stock
```

### Logic ưu tiên đặt hàng:
1. **Đảm bảo tồn kho tối thiểu** (Tồn nhỏ nhất)
2. **Ưu tiên sản phẩm bán nhiều** (số lượng đã bán 4 tuần)
3. **Highlight sản phẩm high-margin** (>20% margin) và high-value (top 20% doanh thu)

---

## ✅ Kiểm tra cuối cùng

```bash
# Tổng số bảng: 25+
# Tổng số dòng: ~100,000+
# Daily data: 169 ngày (2025-09-11 → 2026-03-06)
# PySpark ETL: ✅ Hoạt động với datetime đầy đủ
# Peak days: ✅ Có levels (1,2,3) và impact_days
# Seasonal factors: ✅ Dynamic calculation
# Tất cả tests: PASS
```

---

## 📝 Cập nhật gần đây

| Ngày | Thay đổi |
|------|----------|
| 2026-03-07 | **Thêm `05_ml_tables.sql`** với schema đầy đủ cho ml_forecasts và ml_model_metrics |
| 2026-03-07 | **Cập nhật `00_run_all.sql`** để chạy đủ 5 file SQL initialization |
| 2026-03-07 | **Thêm `ton_nho_nhat`** vào bảng `products` từ DanhSachSanPham |
| 2026-03-07 | **Cập nhật logic purchase order**: MAX(Dự báo, Tồn nhỏ nhất) - Tồn hiện tại |
| 2026-03-07 | **Sắp xếp ưu tiên**: Bán nhiều → Doanh thu → Margin |
| 2026-03-06 | **169 ngày DAILY DATA** - Sửa lỗi lấy datetime từ Excel |
| 2026-03-06 | Thêm `peak_level` và `impact_days` cho seasonal factor |
| 2026-03-06 | PySpark ETL xử lý cả string và datetime object |
| 2026-03-06 | Inventory vào ClickHouse trực tiếp (overwrite mode) |
| 2026-03-06 | ML training với 14,085 records, lag features [1,7,14,30] |
