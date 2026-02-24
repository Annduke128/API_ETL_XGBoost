# 🗺️ VISUAL PIPELINE MAP - TỔNG QUAN HỆ THỐNG

> Tài liệu này mô tả toàn bộ pipeline dữ liệu từ nguồn đến ML models  
> **Cập nhật:** 2026-02-21  
> **Trạng thái:** Đã dọn dẹp các bảng không cần thiết

---

## 📊 Tổng quan các thành phần

| Layer | Thành phần | Số lượng | Mô tả |
|-------|-----------|----------|-------|
| 1 | PostgreSQL Tables | 4 | Database chính lưu dữ liệu gốc |
| 2 | ClickHouse Staging | 3 | Raw data từ PostgreSQL |
| 3 | DBT Staging Models | 4 | Views xử lý cơ bản |
| 4 | DBT Intermediate | 3 | Models trung gian (ephemeral) |
| 5 | DBT Dimensions | 3 | Dimension tables |
| 6 | DBT Facts | 5 | Fact tables cho ML & báo cáo |
| 7 | ML Pipeline | 1 | XGBoost forecasting |

---

## 🔄 DATA FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              🎯 PIPELINE DỮ LIỆU TỔNG QUAN                               │
└─────────────────────────────────────────────────────────────────────────────────────────┘

╔═══════════════════════════════════════════════════════════════════════════════════════╗
║  LAYER 1: DATA SOURCES (Nguồn dữ liệu)                                                ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                       ║
║  ┌───────────────────────────────────────────────────────────────────────────────┐   ║
║  │                    📁 POSTGRESQL (Database chính)                              │   ║
║  │                                                                                │   ║
║  │   ┌──────────────┐    ┌───────────────────┐    ┌──────────────┐             │   ║
║  │   │  products    │    │   transactions    │    │   branches   │             │   ║
║  │   │  (2,090)     │    │      (9,397)      │    │     (1)      │             │   ║
║  │   └──────┬───────┘    └─────────┬─────────┘    └──────┬───────┘             │   ║
║  │          │                      │                     │                     │   ║
║  │          │                      │                     │                     │   ║
║  │          ▼                      ▼                     ▼                     │   ║
║  │   ┌──────────────────────────────────────────────────────────────────────┐  │   ║
║  │   │              transaction_details (20,774)                             │  │   ║
║  │   │         (Chi tiết giao dịch - nhiều sản phẩm/1 giao dịch)             │  │   ║
║  │   └──────────────────────────────────────────────────────────────────────┘  │   ║
║  │                                                                                │   ║
║  └───────────────────────────────────────────────────────────────────────────────┘   ║
║                                    │                                                  ║
║                    sync_to_clickhouse.py (Python script)                              ║
║                                    │                                                  ║
║                                    ▼                                                  ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║  LAYER 2: RAW STAGING (ClickHouse - Chưa qua xử lý)                                   ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                       ║
║   ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────────────┐  ║
║   │  staging_products   │  │ staging_transactions│  │    staging_branches         │  ║
║   │     (2,090 rows)    │  │     (9,397 rows)    │  │         (1 row)             │  ║
║   │   ✓ Sản phẩm        │  │   ✓ Giao dịch       │  │       ✓ Chi nhánh           │  ║
║   │   ✓ 2025-2026       │  │   ✓ 2025-2026       │  │                             │  ║
║   └──────────┬──────────┘  └──────────┬──────────┘  └─────────────┬───────────────┘  ║
║              │                        │                            │                ║
║              │                        │                            │                ║
║              └────────────────────────┼────────────────────────────┘                ║
║                                       │                                              ║
║                                       │                                              ║
║                              DBT Models (dbt run)                                     ║
║                                       │                                              ║
║                    ┌──────────────────┼──────────────────┐                          ║
║                    │                  │                  │                          ║
║                    ▼                  ▼                  ▼                          ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║  LAYER 3: DBT STAGING MODELS (Views)                                                  ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                       ║
║   ┌─────────────────┐  ┌──────────────────┐  ┌────────────────────────────────────┐  ║
║   │  stg_products   │  │ stg_transactions │  │    stg_transaction_details         │  ║
║   │    (VIEW)       │  │     (VIEW)       │  │           (VIEW)                   │  ║
║   │   + Cleaned     │  │   + Date parts   │  │     + Product/branch info          │  ║
║   │   + Renamed     │  │   + Time features│  │     + Line revenue/cost calc       │  ║
║   └────────┬────────┘  └────────┬─────────┘  └──────────────┬─────────────────────┘  ║
║            │                    │                            │                       ║
║            │                    │                            │                       ║
║            └────────────────────┼────────────────────────────┘                       ║
║                                 │                                                     ║
║                                 ▼                                                     ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║  LAYER 4: DBT INTERMEDIATE MODELS (Ephemeral/Views)                                   ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                       ║
║   ┌──────────────────────────┐      ┌─────────────────────────────────────────────┐  ║
║   │  int_product_performance │      │         int_sales_daily                     │  ║
║   │       (EPHEMERAL)        │      │           (EPHEMERAL)                       │  ║
║   │   ✓ ABC classification   │      │    ✓ Daily aggregation by product/branch    │  ║
║   │   ✓ Revenue/quantity     │      │    ✓ Transaction counts                     │  ║
║   └────────────┬─────────────┘      └──────────────────┬──────────────────────────┘  ║
║                │                                        │                            ║
║                │                                        │                            ║
║                └────────────────┬───────────────────────┘                            ║
║                                 │                                                     ║
║                                 ▼                                                     ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║  LAYER 5: DBT MARTS (Dimension & Fact Tables)                                         ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                       ║
║   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                               ║
║   │  dim_date    │  │ dim_product  │  │ dim_branch   │                               ║
║   │  (4,018)     │  │   (2,090)    │  │    (1)       │                               ║
║   │  Date dims   │  │ + ABC class  │  │  Branch info │                               ║
║   └──────────────┘  └──────┬───────┘  └──────────────┘                               ║
║                            │                                                         ║
║                            ▼                                                         ║
║   ┌──────────────────────────────────────────────────────────────────────────────┐  ║
║   │                                                                               │  ║
║   │  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────────────────┐ │  ║
║   │  │  fct_daily_sales │  │ fct_regular_sales│  │  fct_promotional_sales      │ │  ║
║   │  │    (13,937)      │  │    (13,911)  ⭐  │  │       (26)                  │ │  ║
║   │  │  All sales       │  │  ML TRAINING     │  │  Promotions only            │ │  ║
║   │  │  by day/product  │  │  (no promotion)  │  │                             │ │  ║
║   │  └──────────────────┘  └──────────────────┘  └─────────────────────────────┘ │  ║
║   │                                                                               │  ║
║   │  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────────────────┐ │  ║
║   │  │ fct_monthly_sales│  │ fct_inventory_   │  │   fct_rfm_analysis          │ │  ║
║   │  │    (5,446)       │  │  forecast_input  │  │        (1)                  │ │  ║
║   │  │  Monthly agg     │  │    (1,719)       │  │   Customer segments         │ │  ║
║   │  └──────────────────┘  └──────────────────┘  └─────────────────────────────┘ │  ║
║   │                                                                               │  ║
║   └──────────────────────────────────────────────────────────────────────────────┘  ║
║                                       │                                              ║
║                                       ▼                                              ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║  LAYER 6: REPORTS & ML                                                                ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                       ║
║   ┌────────────────────┐      ┌──────────────────────────────────────────────────┐  ║
║   │   rpt_sales_kpi    │      │         ML PIPELINE (xgboost_forecast.py)         │  ║
║   │      (3 rows)      │      │                                                   │  ║
║   │  Summary reports   │      │  ┌─────────────────────────────────────────────┐ │  ║
║   └────────────────────┘      │  │  INPUT: fct_regular_sales                  │ │  ║
║                               │  │  • 158 days (2025-09-11 → 2026-02-15)      │ │  ║
║                               │  │  • 13,911 records                           │ │  ║
║                               │  │  • 2,075 products                           │ │  ║
║                               │  └─────────────────────────────────────────────┘ │  ║
║                               │                          │                        │  ║
║                               │                          ▼                        │  ║
║                               │  ┌─────────────────────────────────────────────┐ │  ║
║                               │  │  OUTPUT: 7-day forecasts                    │ │  ║
║                               │  │  • product_quantity_model.pkl               │ │  ║
║                               │  │  • product_profit_margin_model.pkl          │ │  ║
║                               │  │  • category_trend_model.pkl                 │ │  ║
║                               │  └─────────────────────────────────────────────┘ │  ║
║                               └──────────────────────────────────────────────────┘  ║
╚═══════════════════════════════════════════════════════════════════════════════════════╝
```

---

## 📋 Chi tiết các bảng ClickHouse

### Raw Data (Staging từ PostgreSQL)

| Bảng | Số dòng | Date Range | Mô tả |
|------|---------|------------|-------|
| `staging_products` | 2,090 | N/A | Danh sách sản phẩm từ PostgreSQL |
| `staging_transactions` | 9,397 | 2025-09-11 → 2026-02-15 | Giao dịch từ PostgreSQL |
| `staging_branches` | 1 | N/A | Chi nhánh từ PostgreSQL |

### DBT Models

| Loại | Bảng | Số dòng | Mục đích |
|------|------|---------|----------|
| **Dimension** | `dim_date` | 4,018 | Date dimensions (2020-2030) |
| **Dimension** | `dim_product` | 2,090 | Sản phẩm + ABC classification |
| **Dimension** | `dim_branch` | 1 | Thông tin chi nhánh |
| **Fact** | `fct_daily_sales` | 13,937 | Doanh số hàng ngày |
| **Fact** ⭐ | `fct_regular_sales` | 13,911 | Doanh số thường (KHÔNG khuyến mại) - **ML dùng** |
| **Fact** | `fct_promotional_sales` | 26 | Doanh số khuyến mại |
| **Fact** | `fct_monthly_sales` | 5,446 | Doanh số hàng tháng |
| **Fact** | `fct_inventory_forecast_input` | 1,719 | Dữ liệu cho inventory forecasting |
| **Fact** | `fct_rfm_analysis` | 1 | Phân tích RFM khách hàng |
| **Report** | `rpt_sales_kpi` | 3 | Báo cáo KPI tổng hợp |

---

## 🔗 Luồng dữ liệu tóm tắt

```
PostgreSQL (4 tables: products, transactions, transaction_details, branches)
    ↓ sync_to_clickhouse.py (Python ETL)
ClickHouse staging_* (3 tables: staging_products, staging_transactions, staging_branches)
    ↓ dbt run
ClickHouse DBT Models:
    ├── stg_* (4 views) - Staging models
    ├── int_* (3 ephemeral) - Intermediate processing
    ├── dim_* (3 tables) - Dimension tables
    └── fct_* (5 tables) - Fact tables
    ↓ ML Pipeline
XGBoost Models (3 models) → 7-day Forecasts
```

---

## 📝 Chi tiết ML Pipeline

### Input
- **Bảng:** `fct_regular_sales`
- **Date range:** 2025-09-11 → 2026-02-15 (**158 ngày** ~ 5.2 tháng)
- **Records:** 13,911
- **Products:** 2,075
- **Branches:** 1

### Models
1. **product_quantity_model** - Dự báo số lượng bán (MdAPE)
2. **product_profit_margin_model** - Dự báo biên lợi nhuận (MAE)
3. **category_trend_model** - Xu hướng theo category (MAPE)

### Output
- 7-day forecasts cho từng sản phẩm
- Email báo cáo tự động
- Lưu trữ kết quả dự báo

---

## 🚀 Commands hữu ích

### Rebuild DBT models
```bash
cd /home/annduke/retail_data_pipeline
docker-compose run --rm dbt dbt run
```

### Chạy ML training
```bash
make ml-train
```

### Kiểm tra dữ liệu ClickHouse
```bash
docker-compose exec clickhouse clickhouse-client --query "
SELECT 
    table,
    sum(rows) as total_rows
FROM system.parts
WHERE database = 'retail_dw' AND active = 1
GROUP BY table
ORDER BY table
"
```

---

## 📊 Tổng kết

- ✅ **158 ngày dữ liệu** (2025-09-11 → 2026-02-15)
- ✅ **13,911 records** trong `fct_regular_sales`
- ✅ **2,075 sản phẩm**
- ✅ **ML Pipeline** sử dụng `fct_regular_sales`
- ✅ **Auto skip training** khi không có dữ liệu mới
- ✅ **Datetime handling** đã được fix (trả về date objects)

---

