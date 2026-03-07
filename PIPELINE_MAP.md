# 🗺️ VISUAL PIPELINE MAP - TỔNG QUAN HỆ THỐNG

> Tài liệu này mô tả toàn bộ pipeline dữ liệu từ nguồn đến ML models  
> **Cập nhật:** 2026-03-06  
> **Trạng thái:** ✅ 169 ngày DAILY DATA - Peak Days với Levels

---

## 📊 Tổng quan các thành phần

| Layer | Thành phần | Số lượng | Mô tả |
|-------|-----------|----------|-------|
| 1 | Excel Files | 3 loại | Nguồn dữ liệu thô |
| 2 | PySpark ETL | 3 scripts | Xử lý song song với Spark |
| 3 | PostgreSQL Tables | 5 | Database chính lưu dữ liệu gốc |
| 4 | ClickHouse Staging | 4 | Raw data + Inventory cho ML |
| 5 | DBT Staging Models | 4 | Views xử lý cơ bản |
| 6 | DBT Intermediate | 4 | Models trung gian |
| 7 | DBT Dimensions | 4 | Dimension tables |
| 8 | DBT Facts | 6 | Fact tables cho ML & báo cáo |
| 9 | ML Pipeline | 1 | XGBoost forecasting |

**📊 Dữ liệu hiện có:**
- **169 ngày** daily data (2025-09-11 → 2026-03-06)
- **14,085 records** trong `fct_regular_sales`
- **7,197 peak days** với seasonal factors

---

## 🔥 PYSPARK ETL ARCHITECTURE

### Data Flow mới

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              🔥 PYSPARK ETL PIPELINE                                     │
└─────────────────────────────────────────────────────────────────────────────────────────┘

╔═══════════════════════════════════════════════════════════════════════════════════════╗
║  LAYER 1: DATA SOURCES (Excel Files)                                                  ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                       ║
║  ┌──────────────────────────┐  ┌──────────────────────────┐  ┌─────────────────────┐ ║
║  │ DanhSachSanPham_*.xlsx   │  │ BaoCaoXuatNhapTon_*.xlsx │  │ BaoCaoBanHang_*.xlsx│ ║
║  │ (16,025 products)        │  │ (1,765 inventory/week)   │  │ (7,947 transactions)│ ║
║  │                          │  │                          │  │                     │ ║
║  │ • Mã hàng                │  │ • Tồn đầu/cuối kỳ       │  │ • Giao dịch         │ ║
║  │ • Giá vốn/bán           │  │ • SL nhập/xuất          │  │ • Doanh thu         │ ║
║  │ • Nhóm hàng 3 cấp       │  │ • **ton_cuoi_ky** ⭐    │  │ • Chi tiết SP       │ ║
║  └───────────┬──────────────┘  └───────────┬──────────────┘  └──────────┬────────────┘ ║
║              │                             │                            │              ║
║              │                             │                            │              ║
║              ▼                             ▼                            ▼              ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║  LAYER 2: PYSPARK ETL SCRIPTS (Parallel Processing)                                   ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                       ║
║  ┌──────────────────────────────┐  ┌──────────────────────────────┐                  ║
║  │ import_products_spark.py     │  │ import_inventory_spark.py    │                  ║
║  │                              │  │                              │                  ║
║  │ • Đọc Excel (pandas)        │  │ • Đọc Excel (pandas)        │                  ║
║  │ • Spark DF processing       │  │ • Spark DF processing       │                  ║
║  │ • Upsert PostgreSQL         │  │ • Upsert PostgreSQL         │                  ║
║  │ • ❌ Không vào ClickHouse   │  │ • ✅ GHI TRỰC TIẾP CH       │                  ║
║  │                              │  │   (Overwrite mode)          │                  ║
║  │                              │  │                              │                  ║
║  └──────────────┬───────────────┘  └──────────┬───────────────────┘                  ║
║                 │                             │                                       ║
║                 │                             │                                       ║
║  ┌──────────────┴───────────────┐  ┌─────────┴──────────────────┐                   ║
║  │  PostgreSQL.products         │  │  PostgreSQL.inventory      │                   ║
║  │  (16,025 rows)               │  │  _transactions (1,765)     │                   ║
║  └──────────────┬───────────────┘  └─────────┬──────────────────┘                   ║
║                 │                             │                                       ║
║                 │                    ┌────────┴────────┐                              ║
║                 │                    │                 │                              ║
║                 │                    ▼                 ▼                              ║
║                 │  ┌──────────────────────────┐  ┌──────────────────────────────┐    ║
║                 │  │ ClickHouse.staging_      │  │                              │    ║
║                 │  │ inventory_transactions   │  │   (Direct JDBC write)        │    ║
║                 │  │ (1,765 rows) ⭐          │  │                              │    ║
║                 │  │                          │  │   • ton_cuoi_ky              │    ║
║                 │  │ • Engine: MergeTree      │  │   • sl_nhap/xuat             │    ║
║                 │  │ • Order by: (date,       │  │   • ton_dau_ky               │    ║
║                 │  │   ma_vach, chi_nhanh)    │  │                              │    ║
║                 │  └──────────────────────────┘  └──────────────────────────────┘    ║
║                 │                                                                     ║
║                 │                              ┌─────────────────────────────┐       ║
║                 │                              │ import_sales_spark.py       │       ║
║                 │                              │                             │       ║
║                 │                              │ • **LẤY DATETIME TỪ EXCEL** │       ║
║                 │                              │   (cột "Thởi gian (theo      │       ║
║                 │                              │    giao dịch)")              │       ║
║                 │                              │ • 169 ngày daily data         │       ║
║                 │                              │ • Chỉ vào PostgreSQL          │       ║
║                 │                              └─────────────┬───────────────┘       ║
║                 │                                            │                       ║
║                 │                              ┌─────────────┴─────────────┐         ║
║                 │                              │ PostgreSQL.transactions   │         ║
║                 │                              │ (7,947 rows, 169 days)    │         ║
║                 │                              └─────────────┬─────────────┘         ║
║                 │                                            │                       ║
║                 └────────────────────────────────────────────┼───────────────────────┘
║                                                              │                       ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║  LAYER 3: SYNC & DBT TRANSFORM                                                        ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║                                                              │                       ║
║                                          sync_to_clickhouse.py                        ║
║                                                              │                       ║
║                                                              ▼                       ║
║  ┌──────────────────────────────────────────────────────────────────────────────┐   ║
║  │                    ClickHouse Staging Tables                                  │   ║
║  │                                                                               │   ║
║  │  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐   │   ║
║  │  │  staging_products   │  │ staging_transactions│  │ staging_trans_      │   │   ║
║  │  │     (16,025)        │  │     (7,947)         │  │ action_details      │   │   ║
║  │  │                     │  │   **169 days** ⭐   │  │     (17,262)        │   │   ║
║  │  └──────────┬──────────┘  └──────────┬──────────┘  └──────────┬──────────┘   │   ║
║  │             │                        │                        │              │   ║
║  │             └────────────────────────┼────────────────────────┘              │   ║
║  │                                      │                                         │   ║
║  │                                    dbt run                                     │   ║
║  │                                      │                                         │   ║
║  │                                      ▼                                         │   ║
║  │  ┌────────────────────────────────────────────────────────────────────────┐   │   ║
║  │  │                    DBT Models (21 models)                               │   │   ║
║  │  │                                                                         │   │   ║
║  │  │  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────────────┐ │   │   ║
║  │  │  │  stg_products   │  │ stg_transactions │  │  stg_trans_details     │ │   │   ║
║  │  │  │    (VIEW)       │  │     (VIEW)       │  │       (VIEW)           │ │   │   ║
║  │  │  │   + Cleaned     │  │   + 169 days     │  │     + Product info     │ │   │   ║
║  │  │  │   + Renamed     │  │   + Date parts   │  │     + Line calc        │ │   │   ║
║  │  │  └────────┬────────┘  └────────┬─────────┘  └──────────┬─────────────┘ │   │   ║
║  │  │           │                    │                       │               │   │   ║
║  │  │           └────────────────────┼───────────────────────┘               │   │   ║
║  │  │                                │                                       │   │   ║
║  │  │                                ▼                                       │   │   ║
║  │  │  ┌──────────────────────────────────────────────────────────────────┐ │   │   ║
║  │  │  │              int_dynamic_seasonal_factor ⭐                       │ │   │   ║
║  │  │  │                                                                  │ │   │   ║
║  │  │  │  • Peak days với levels (1, 2, 3)                              │ │   │   ║
║  │  │  │  • Impact days (1, 7, 14)                                      │ │   │   ║
║  │  │  │  • seasonal_factor, revenue_factor, quantity_factor            │ │   │   ║
║  │  │  │  • is_peak_day, peak_level                                     │ │   │   ║
║  │  │  │                                                                  │ │   │   ║
║  │  │  │  Peak Days:                                                    │ │   │   ║
║  │  │  │  • Level 3 (14 days): Tet Nguyen Dan (1-3/1)                   │ │   │   ║
║  │  │  │  • Level 2 (7 days): Gio To, Quoc te Lao dong, Back to school  │ │   │   ║
║  │  │  │  • Level 1 (1 day): Valentine, Black Friday, Countdown         │ │   │   ║
║  │  │  │                                                                  │ │   │   ║
║  │  │  └────────────────────────┬───────────────────────────────────────┘ │   │   ║
║  │  │                           │                                         │   │   ║
║  │  │                           ▼                                         │   │   ║
║  │  │  ┌──────────────────────────────────────────────────────────────────┐ │   │   ║
║  │  │  │                         FACT TABLES                               │ │   │   ║
║  │  │  │                                                                     │ │   │   ║
║  │  │  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │ │   │   ║
║  │  │  │  │  fct_daily_sales │  │ fct_regular_sales│  │fct_daily_sales_  │ │ │   │   ║
║  │  │  │  │    (14,085)      │  │    (14,085)  ⭐  │  │  with_seasonal   │ │ │   │   ║
║  │  │  │  │  169 days        │  │  ML TRAINING     │  │    (14,085)      │ │ │   │   ║
║  │  │  │  │  by day/product  │  │  169 days        │  │  169 days        │ │ │   │   ║
║  │  │  │  └──────────────────┘  └──────────────────┘  └──────────────────┘ │ │   │   ║
║  │  │  │                                                                     │ │   │   ║
║  │  │  │  ┌──────────────────┐  ┌──────────────────┐                        │ │   │   ║
║  │  │  │  │fct_monthly_sales │  │fct_inventory_    │                        │ │   │   ║
║  │  │  │  │    (14,085)      │  │  forecast_input  │                        │ │   │   ║
║  │  │  │  │  Monthly agg     │  │    (1,472)       │                        │ │   │   ║
║  │  │  │  └──────────────────┘  └──────────────────┘                        │ │   │   ║
║  │  │  │                                                                     │ │   │   ║
║  │  │  └─────────────────────────────────────────────────────────────────────┘ │   │   ║
║  │  │                                                                            │   │   ║
║  │  └──────────────────────────────────────────────────────────────────────────┘   │   ║
║  │                                                                                   │   ║
║  └───────────────────────────────────────────────────────────────────────────────────┘   ║
║                                                                                          ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║  LAYER 4: ML PIPELINE                                                                 ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                          ║
║  ┌─────────────────────────────────────────────────────────────────────────────────┐  ║
║  │                         ML PIPELINE (xgboost_forecast.py)                        │  ║
║  │                                                                                  │  ║
║  │  ┌───────────────────────────────────────────────────────────────────────────┐  │  ║
║  │  │                           INPUTS (169 days)                                │  │  ║
║  │  │  ┌──────────────────┐  ┌────────────────────────┐  ┌──────────────┐      │  │  ║
║  │  │  │ fct_regular_sales│  │ staging_inventory_     │  │   dim_product│      │  │  ║
║  │  │  │ • 169 days ⭐    │  │ transactions           │  │ • ABC class  │      │  │  ║
║  │  │  │ • 14,085 records │  │ • ton_cuoi_ky ⭐       │  │ • Attributes │      │  │  ║
║  │  │  │ • 2,090 products │  │ • Current stock        │  │              │      │  │  ║
║  │  │  └────────┬─────────┘  └───────────┬────────────┘  └──────┬───────┘      │  │  ║
║  │  │           │                        │                      │              │  │  ║
║  │  │           └────────────────────────┼──────────────────────┘              │  │  ║
║  │  │                                    │                                      │  │  ║
║  │  │                                    ▼                                      │  │  ║
║  │  │  ┌─────────────────────────────────────────────────────────────────────┐ │  │  ║
║  │  │  │                      FEATURE ENGINEERING                            │ │  │  ║
║  │  │  │                                                                       │ │  │  ║
║  │  │  │  Lag Features: [1, 7, 14, 30] (vì có 169 ngày)                     │ │  │  ║
║  │  │  │  Seasonal Features: is_peak_day, peak_level, seasonal_factor        │ │  │  ║
║  │  │  │  Time Features: day_of_week, day_of_month, week_of_year             │ │  │  ║
║  │  │  │  Rolling: rolling_mean_7, rolling_mean_14, rolling_mean_30          │ │  │  ║
║  │  │  │                                                                       │ │  │  ║
║  │  │  └─────────────────────────────────────────────────────────────────────┘ │  │  ║
║  │  │                                    │                                      │  │  ║
║  │  │                                    ▼                                      │  │  ║
║  │  │  ┌─────────────────────────────────────────────────────────────────────┐ │  │  ║
║  │  │  │                      FORECAST CALCULATION                           │ │  │  ║
║  │  │  │                                                                       │ │  │  ║
║  │  │  │  predicted_demand = XGBoost.predict(14,085 daily records)          │ │  │  ║
║  │  │  │  current_stock = staging_inventory_transactions.ton_cuoi_ky         │ │  │  ║
║  │  │  │  min_stock = business_rule(dim_product.abc_class)                  │ │  │  ║
║  │  │  │                                                                       │ │  │  ║
║  │  │  │  required_purchase = max(predicted_demand, min_stock)              │ │  │  ║
║  │  │  │                      - current_stock                                │ │  │  ║
║  │  │  │                                                                       │ │  │  ║
║  │  │  └─────────────────────────────────────────────────────────────────────┘ │  │  ║
║  │  │                                    │                                      │  │  ║
║  │  │                                    ▼                                      │  │  ║
║  │  │  ┌─────────────────────────────────────────────────────────────────────┐ │  │  ║
║  │  │  │                         OUTPUTS                                     │ │  │  ║
║  │  │  │  • product_quantity_model.pkl                                       │ │  │  ║
║  │  │  │  • category_trend_model.pkl                                         │ │  │  ║
║  │  │  │  • 7-day forecasts per product                                      │ │  │  ║
║  │  │  │  • Purchase recommendations                                         │ │  │  ║
║  │  │  └─────────────────────────────────────────────────────────────────────┘ │  │  ║
║  │  │                                                                           │  │  ║
║  │  └───────────────────────────────────────────────────────────────────────────┘  │  ║
║  │                                                                                  │  ║
║  └──────────────────────────────────────────────────────────────────────────────────┘  ║
╚═══════════════════════════════════════════════════════════════════════════════════════╝
```

---

## 🔑 Key Design Decisions

### 1. Daily Data từ Excel

| Vấn đề | Giải pháp | Kết quả |
|--------|-----------|---------|
| **Datetime trong Excel** | Lấy từ cột "Thởi gian (theo giao dịch)" | **169 ngày** ✅ |
| **Unicode normalization** | Dùng `unicodedata.normalize('NFC')` | Tìm đúng cột ✅ |
| **String vs Datetime** | Hỗ trợ cả 2 kiểu trong code | Parse chính xác ✅ |

### 2. Inventory vào ClickHouse trực tiếp

| Aspect | Implementation | Lý do |
|--------|---------------|-------|
| **Script** | `import_inventory_spark.py` | Xử lý song song với Spark |
| **Mode** | Overwrite | Tránh duplicates khi re-import |
| **Engine** | MergeTree | Tối ưu cho time-series data |
| **Order by** | (ngay_bao_cao, ma_vach, chi_nhanh) | Query nhanh theo ngày + sản phẩm |

### 3. Peak Days với Levels

| Level | Ngày | Impact | Ví dụ |
|-------|------|--------|-------|
| **1** | 1 | 1 ngày | Valentine, Black Friday, Countdown |
| **2** | 7 | 7 ngày (1 tuần) | Gio To, Quoc te Lao dong, Back to school |
| **3** | 14 | 14 ngày (2 tuần) | Tet Nguyen Dan (1-3/1) |

---

## 📋 Chi tiết các bảng ClickHouse

### Raw Data (Từ PySpark ETL)

| Bảng | Số dòng | Nguồn | Mode | Mô tả |
|------|---------|-------|------|-------|
| `staging_inventory_transactions` | 1,765 | PySpark Direct | Overwrite | ⭐ Tồn kho cho ML |

### Raw Data (Từ dbt sync)

| Bảng | Số dòng | Nguồn | Mô tả |
|------|---------|-------|-------|
| `staging_products` | 16,025 | PostgreSQL via dbt | Danh sách sản phẩm |
| `staging_transactions` | 7,947 | PostgreSQL via dbt | Giao dịch **169 ngày** ⭐ |
| `staging_transaction_details` | 17,262 | PostgreSQL via dbt | Chi tiết giao dịch |

### DBT Models

| Loại | Bảng | Số dòng | Mô tả |
|------|------|---------|-------|
| **Dimension** | `dim_date` | 4,018 | Date dimensions |
| **Dimension** | `dim_product` | 16,025 | Sản phẩm + ABC classification |
| **Dimension** | `dim_branch` | 1 | Thông tin chi nhánh |
| **Fact** ⭐ | `fct_regular_sales` | 14,085 | **ML Training - 169 days** |
| **Fact** ⭐ | `fct_inventory_forecast_input` | 1,472 | **Inventory Forecasting** |
| **Fact** | `fct_daily_sales` | 14,085 | Doanh số hàng ngày **169 ngày** |
| **Fact** | `fct_daily_sales_with_seasonal` | 14,085 | Có seasonal features **169 ngày** |
| **Fact** | `fct_promotional_sales` | 23 | Doanh số khuyến mại |
| **Fact** | `fct_monthly_sales` | 14,085 | Doanh số hàng tháng |
| **View** | `int_dynamic_seasonal_factor` | 3 | Peak days với levels (1,2,3) |
| **Report** | `rpt_sales_kpi` | 3 | Báo cáo KPI tổng hợp |

---

## 🔧 Technical Stack

| Component | Technology | Version |
|-----------|------------|---------|
| ETL Engine | PySpark | 4.1.1 |
| JDBC Drivers | PostgreSQL + ClickHouse | 42.6.0 + 0.6.0 |
| Database (Source) | PostgreSQL | 15-alpine |
| Database (Analytics) | ClickHouse | 24-alpine |
| Transformation | dbt | 1.7.0 |
| ML Framework | XGBoost | Latest |
| Orchestration | Apache Airflow | 2.8.0 |

---

## 🚀 Commands hữu ích

### Chạy PySpark ETL
```bash
cd /home/annduke/project/Hasu_ML_k3s/docker
make smart-process
```

### Rebuild DBT models
```bash
cd /home/annduke/project/Hasu_ML_k3s/docker
docker-compose run --rm dbt dbt run
```

### Chạy ML training
```bash
cd /home/annduke/project/Hasu_ML_k3s/docker
make ml-train
```

### Kiểm tra daily data
```bash
# PostgreSQL
docker exec -i retail_postgres psql -U retail_user -d retail_db -c "
  SELECT DATE(thoi_gian) as date, COUNT(*) 
  FROM transactions 
  GROUP BY date 
  ORDER BY date;
"

# ClickHouse
docker exec -i retail_clickhouse clickhouse-client -q "
  SELECT transaction_date, count() 
  FROM retail_dw.fct_regular_sales 
  GROUP BY transaction_date 
  ORDER BY transaction_date;
"
```

---

## 📊 Peak Days Reference

| Tháng | Ngày | Sự kiện | Level | Impact Days |
|-------|------|---------|-------|-------------|
| 1 | 1-3 | Tet Nguyen Dan | 3 | 14 |
| 2 | 14 | Valentine | 1 | 1 |
| 3 | 8 | Quoc te Nu | 1 | 1 |
| 4 | 30 | Gio To | 2 | 7 |
| 5 | 1 | Quoc te Lao dong | 2 | 7 |
| 6 | 1 | Quoc te Thieu nhi | 1 | 1 |
| 7 | 1 | Cao diem he | 2 | 7 |
| 8 | 15 | Back to school | 2 | 7 |
| 9 | 2 | Thu sang | 2 | 7 |
| 10 | 20 | Cuoi nam | 2 | 7 |
| 11 | 11 | Black Friday | 1 | 1 |
| 11 | 29 | Sale cuoi nam | 2 | 7 |
| 12 | 24-25 | Giang sinh | 2/1 | 7/1 |
| 12 | 31 | Countdown | 1 | 1 |

---

## 📈 Performance Metrics

| Metric | Value |
|--------|-------|
| Daily data days | **169** |
| Total sales records | **14,085** |
| Products | 2,090 |
| ML lag features | [1, 7, 14, 30] |
| Peak days detected | 7,197 |
| Avg seasonal factor | 0.36 |
| Top feature | seasonal_factor (0.25 importance) |

---

## 📝 Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-03-06 | **169 ngày DAILY DATA** - Sửa lỗi datetime từ Excel | AI Assistant |
| 2026-03-06 | Thêm `peak_level` (1,2,3) và `impact_days` | AI Assistant |
| 2026-03-06 | Unicode normalization cho cột Excel | AI Assistant |
| 2026-03-06 | ML training với lag features [1,7,14,30] | AI Assistant |
| 2026-03-06 | Inventory vào ClickHouse trực tiếp | AI Assistant |
