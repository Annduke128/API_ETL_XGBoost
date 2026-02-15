# Retail Data Pipeline - Hệ thống Data Warehouse cho ngành bán lẻ

Hệ thống data pipeline hoàn chỉnh với ETL tự động, Data Warehouse, BI Dashboard và ML Forecasting.

## 📋 Mục lục

1. [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
2. [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
3. [Cài đặt và khởi động](#cài-đặt-và-khởi-động)
4. [Kiểm tra healthcheck](#kiểm-tra-healthcheck)
5. [Import dữ liệu CSV](#import-dữ-liệu-csv)
6. [Chạy DBT Project](#chạy-dbt-project)
7. [Chạy ML Models](#chạy-ml-models)
8. [Tùy chỉnh tham số](#tùy-chỉnh-tham-số)
9. [Kết nối Superset BI](#kết-nối-superset-bi)
10. [Troubleshooting](#troubleshooting)

---

## 🏗️ Kiến trúc hệ thống

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│  CSV Input  │────▶│   Cleaner   │────▶│  PostgreSQL     │
└─────────────┘     └─────────────┘     │  (OLTP)         │
                                        └────────┬────────┘
                                                 │
                   ┌─────────────┐              │
                   │    Redis    │◄─────────────┤
                   │   (Buffer)  │              │
                   └─────────────┘              │
                                                ▼
                                        ┌─────────────────┐
                                        │   ClickHouse    │
                                        │  (Data Warehouse)
                                        └────────┬────────┘
                                                 │
         ┌──────────────┬────────────────────────┘              ▲
         ▼              ▼                                       │
   ┌──────────┐   ┌──────────┐                            ┌──────────┐
   │   DBT    │   │   ML/XGB │                            │ Superset │
   │Transform │   │ Forecast │                            │   (BI)   │
   └──────────┘   └──────────┘                            └──────────┘
         │                                               ▲
         └──────────────────┬────────────────────────────┘
                            ▼
                     ┌──────────────┐
                     │   Airflow    │
                     │ (Scheduler)  │
                     └──────────────┘
```

### Các thành phần chính:

| Service | Port | Mô tả |
|---------|------|-------|
| **PostgreSQL** | 5432 | OLTP Database - Lưu giao dịch thờigian thực |
| **ClickHouse** | 8123 (HTTP), 9000 (Native) | Data Warehouse - Phân tích dữ liệu lớn |
| **Redis** | 6379 | Buffer & Cache |
| **Airflow** | 8085 | Workflow Scheduler |
| **Superset** | 8088 | BI Dashboard |

---

## 💻 Yêu cầu hệ thống

### Tối thiểu:
- **RAM**: 8GB
- **Disk**: 20GB free
- **Docker**: 24.0+
- **Docker Compose**: 2.20+

### Khuyến nghị:
- **RAM**: 16GB+
- **CPU**: 4 cores+
- **Disk**: 50GB+ SSD

---

## 🚀 Cài đặt và khởi động

### Bước 1: Clone và vào thư mục

```bash
cd /home/annduke/retail_data_pipeline
```

### Bước 2: Copy file môi trường

```bash
cp .env.example .env
```

### Bước 3: Khởi động core services

```bash
# Khởi động các service chính
docker-compose up -d postgres clickhouse redis

# Đợi 30-60s cho các service khởi động
sleep 30
```

### Bước 4: Khởi động Airflow và Superset

```bash
# Khởi động Airflow
docker-compose up -d airflow-init airflow-webserver airflow-scheduler

# Khởi động Superset
docker-compose up -d superset-init superset-web

# Đợi khởi tạo xong (khoảng 1-2 phút)
sleep 60
```

### Bước 5: Kiểm tra tất cả services

```bash
docker-compose ps
```

---

## 🔍 Kiểm tra Healthcheck

### 1. Kiểm tra tổng quan

```bash
# Xem status tất cả containers
docker-compose ps

# Xem logs một service
docker-compose logs -f postgres
docker-compose logs -f clickhouse
docker-compose logs -f superset-web
```

### 2. Kiểm tra PostgreSQL

```bash
# Test connection
docker-compose exec -T postgres pg_isready -U retail_user -d retail_db

# Xem dữ liệu
docker-compose exec -T postgres psql -U retail_user -d retail_db -c "
  SELECT 
    'branches' as table_name, COUNT(*) as count FROM branches
  UNION ALL
  SELECT 'products', COUNT(*) FROM products
  UNION ALL
  SELECT 'transactions', COUNT(*) FROM transactions;
"
```

### 3. Kiểm tra ClickHouse

```bash
# Test connection
docker-compose exec -T clickhouse clickhouse-client -q "SELECT 1"

# Xem tables
docker-compose exec -T clickhouse clickhouse-client -q "SHOW TABLES FROM retail_dw"

# Xem dữ liệu
docker-compose exec -T clickhouse clickhouse-client -q "
  SELECT COUNT(*) FROM retail_dw.fact_transactions
"
```

### 4. Kiểm tra Redis

```bash
# Test ping
docker-compose exec -T redis redis-cli ping

# Xem keys
docker-compose exec -T redis redis-cli KEYS "*"
```

### 5. Kiểm tra Superset

```bash
# Health check
curl http://localhost:8088/health

# Login page
curl -I http://localhost:8088/login
```

---

## 📁 Import dữ liệu CSV

### Tự động (Airflow Schedule)

Hệ thống tự động import CSV **hàng ngày lúc 2h sáng** thông qua Airflow DAG `csv_daily_import`:

```
02:00 AM Daily
    ├── Quét file CSV trong csv_input/
    ├── Làm sạch & Import vào PostgreSQL + ClickHouse
    └── Chạy DBT Transform
```

### Import thủ công (Manual)

Nếu cần import ngay lập tức:

```bash
# Copy file CSV vào thư mục
cp /path/to/your/file.csv csv_input/

# Chạy import (chỉ xử lý 1 lần)
make csv-import

# Hoặc import + chạy DBT transform
make csv-process-full
```

### Kiểm tra kết quả import:

```bash
# PostgreSQL
docker-compose exec -T postgres psql -U retail_user -d retail_db -c "
  SELECT 
    'branches' as table_name, COUNT(*) as count FROM branches
  UNION ALL
  SELECT 'products', COUNT(*) FROM products
  UNION ALL
  SELECT 'transactions', COUNT(*) FROM transactions
  UNION ALL
  SELECT 'transaction_details', COUNT(*) FROM transaction_details;
"

# ClickHouse
docker-compose exec -T clickhouse clickhouse-client -q "
  SELECT COUNT(*) FROM retail_dw.fact_transactions
"
```

---

## 🔧 Chạy DBT Project

### Cấu trúc DBT:

```
dbt_retail/
├── models/
│   ├── staging/          # Làm sạch dữ liệu gốc
│   ├── intermediate/     # Transform trung gian
│   └── marts/            # Facts & Dimensions
│       ├── core/         # dim_date, dim_product, dim_branch
│       ├── sales/        # fct_daily_sales, fct_monthly_sales
│       ├── inventory/    # fct_inventory_forecast_input
│       └── customers/    # fct_rfm_analysis
├── seeds/                # Dữ liệu tham chiếu (product.csv, seasonality)
└── macros/               # Hàm tiện ích
```

### Các bước chạy DBT:

#### 1. Cài dependencies

```bash
docker-compose run --rm \
  -e POSTGRES_HOST=postgres \
  -e POSTGRES_PORT=5432 \
  -e POSTGRES_USER=retail_user \
  -e POSTGRES_PASSWORD=retail_password \
  -e POSTGRES_DB=retail_db \
  dbt deps
```

#### 2. Load seeds (dữ liệu tham chiếu)

```bash
docker-compose run --rm \
  -e POSTGRES_HOST=postgres \
  -e POSTGRES_PORT=5432 \
  -e POSTGRES_USER=retail_user \
  -e POSTGRES_PASSWORD=retail_password \
  -e POSTGRES_DB=retail_db \
  dbt seed
```

#### 3. Chạy tất cả models

```bash
docker-compose run --rm \
  -e POSTGRES_HOST=postgres \
  -e POSTGRES_PORT=5432 \
  -e POSTGRES_USER=retail_user \
  -e POSTGRES_PASSWORD=retail_password \
  -e POSTGRES_DB=retail_db \
  dbt run
```

#### 4. Chạy specific models

```bash
# Chỉ chạy staging models
docker-compose run --rm \
  -e POSTGRES_HOST=postgres \
  dbt run --select staging

# Chạy một model cụ thể
docker-compose run --rm \
  -e POSTGRES_HOST=postgres \
  dbt run --select stg_transactions

# Chạy marts sales
docker-compose run --rm \
  -e POSTGRES_HOST=postgres \
  dbt run --select marts.sales
```

#### 5. Chạy tests

```bash
docker-compose run --rm \
  -e POSTGRES_HOST=postgres \
  dbt test
```

#### 6. Generate và serve docs

```bash
# Generate docs
docker-compose run --rm \
  -e POSTGRES_HOST=postgres \
  dbt docs generate

# Serve docs (truy cập http://localhost:8080)
docker-compose run --rm \
  -e POSTGRES_HOST=postgres \
  -p 8080:8080 \
  dbt docs serve --host 0.0.0.0 --port 8080
```

---

## 🤖 Chạy ML Models

Hệ thống sử dụng **XGBoost** kết hợp **Optuna** (Bayesian Optimization) để tự động tìm hyperparameters tối ưu.

### 1. Training với Optuna Tuning (Recommended)

```bash
# Train với Optuna (50 trials - default, ~10-15 phút)
make ml-train

# Train tối ưu hơn (100 trials, ~20-30 phút)
make ml-train-optimal

# Train nhanh (không tuning, ~2-3 phút)
make ml-train-fast

# Train + Generate forecasts
make ml-train-predict
```

### 2. Chi tiết Hyperparameter Tuning

Hệ thống tự động tìm kiếm hyperparameters tối ưu:

| Parameter | Range | Ý nghĩa |
|-----------|-------|---------|
| `max_depth` | 3-10 | Độ sâu cây |
| `learning_rate` | 0.01-0.3 | Tốc độ học |
| `subsample` | 0.6-1.0 | Sampling ratio |
| `colsample_bytree` | 0.6-1.0 | Feature sampling |
| `reg_alpha/lambda` | 1e-8 - 10 | Regularization |
| `min_child_weight` | 1-10 | Min samples per leaf |

Kết quả tuning được lưu tại:
```
ml_pipeline/models/
├── product_quantity_model.pkl
├── product_revenue_model.pkl
├── category_quantity_model.pkl
├── training_metrics.json          # Metrics & best params
└── *_optuna_study.pkl            # Optuna studies
```

### 3. Airflow DAG tự động

DAG `retail_weekly_ml` sẽ tự động chạy vào 3h sáng Chủ nhật hàng tuần.

Kiểm tra DAG:
```bash
# Vào Airflow UI: http://localhost:8085 (admin/admin)
# Trigger DAG thủ công
```

### 3. Xem kết quả dự báo

```bash
# Trong PostgreSQL
docker-compose exec -T postgres psql -U retail_user -d retail_db -c "
  SELECT * FROM ml_forecasts 
  ORDER BY forecast_date DESC 
  LIMIT 10;
"
```

---

## ⚙️ Tùy chỉnh tham số

### 1. Tham số trong dbt_project.yml

```yaml
# retail_data_pipeline/dbt_retail/dbt_project.yml

vars:
  # Biến cho ngành bán lẻ
  min_date: '2020-01-01'
  currency: 'VND'
  
  # Ngưỡng phân loại giao dịch
  high_value_threshold: 1000000  # 1 triệu VND
  
  # Phân loại ABC (80/15/5 rule)
  abc_a_threshold: 0.8   # Top 80% doanh thu
  abc_b_threshold: 0.95  # 80-95% doanh thu
  
  # Phân loại RFM
  rfm_recency_high: 7    # Ngày
  rfm_recency_medium: 30
  rfm_frequency_high: 10
  rfm_monetary_high: 5000000
```

**Sửa xong chạy lại:**
```bash
docker-compose run --rm -e POSTGRES_HOST=postgres dbt run
```

### 2. Tham số ML trong xgboost_forecast.py

```python
# retail_data_pipeline/ml_pipeline/xgboost_forecast.py

# Cách 1: Sử dụng Optuna Tuning (Recommended)
# Tự động tìm hyperparameters tối ưu
forecaster.train_all_models(
    use_tuning=True,
    tuning_method='optuna',
    n_trials=50,           # Số lần thử nghiệm
    days=365               # Số ngày lịch sử
)

# Cách 2: Manual hyperparameters (nhanh hơn)
model = xgb.XGBRegressor(
    objective='reg:squarederror',
    n_estimators=500,        # Số cây
    max_depth=6,             # Độ sâu tối đa
    learning_rate=0.1,       # Tốc độ học
    subsample=0.8,           # Tỷ lệ mẫu
    colsample_bytree=0.8,    # Tỷ lệ cột
    random_state=42
)

# Lead time cho inventory
lead_time_days = 7
```

### 3. Tham số CSV Processor

```python
# retail_data_pipeline/data_cleaning/csv_processor.py

# Ngưỡng phân loại ABC
abc_a_threshold = 0.8
abc_b_threshold = 0.95

# Ngưỡng giá trị giao dịch
high_value_threshold = 1000000

# Encoding
encoding_priority = ['utf-8', 'utf-8-sig', 'utf-16', 'cp1252']
```

### 4. Tham số Docker Compose

```yaml
# retail_data_pipeline/docker-compose.yml

services:
  postgres:
    environment:
      POSTGRES_USER: retail_user      # Thay đổi user
      POSTGRES_PASSWORD: your_pass    # Thay đổi password
      POSTGRES_DB: retail_db          # Thay đổi DB name
    
  clickhouse:
    environment:
      CLICKHOUSE_PASSWORD: your_pass  # Thay đổi password
```

**Apply thay đổi:**
```bash
docker-compose down
docker-compose up -d
```

---

## 📊 Kết nối Superset BI

### 1. Truy cập UI

- URL: http://localhost:8088
- Username: `admin`
- Password: `admin`

### 2. Thêm Database Connection

**PostgreSQL:**
- Database Name: `Retail PostgreSQL`
- SQLAlchemy URI: `postgresql://retail_user:retail_password@postgres:5432/retail_db`

**ClickHouse:**
- Database Name: `Retail ClickHouse`
- SQLAlchemy URI: `clickhouse+http://default:clickhouse_password@clickhouse:8123/retail_dw`

### 3. Tạo Dataset

**Datasets → + Dataset**
- Chọn Database → Schema → Table
- Tables sẵn có sau khi chạy DBT:
  - `staging.stg_transactions`
  - `marts.fct_daily_sales`
  - `marts.fct_monthly_sales`
  - `marts.fct_rfm_analysis`
  - `marts.dim_product`
  - `marts.dim_branch`

### 4. Tạo Chart mẫu

**Chart 1: Doanh thu theo chi nhánh**
```
Chart Type: Bar Chart
Dataset: fct_daily_sales
X-axis: chi_nhanh
Metric: SUM(doanh_thu)
```

**Chart 2: Top sản phẩm bán chạy**
```
Chart Type: Table
Dataset: stg_transaction_details
Group by: ten_hang
Metrics: SUM(so_luong), SUM(line_revenue)
Row Limit: 10
Sort: so_luong DESC
```

---

## 🛠️ Troubleshooting

### Lỗi 1: Port đã được sử dụng

```bash
# Kiểm tra port
sudo lsof -i :5432
sudo lsof -i :8088

# Thay đổi port trong docker-compose.yml
# Ví dụ: thay "8080:8080" thành "8085:8080"
```

### Lỗi 2: Container unhealthy

```bash
# Restart container
docker-compose restart clickhouse

# Xem logs chi tiết
docker-compose logs clickhouse

# Reset hoàn toàn
docker-compose down -v
docker-compose up -d
```

### Lỗi 3: DBT connection refused

```bash
# Đảm bảo set đúng environment variables
docker-compose run --rm \
  -e POSTGRES_HOST=postgres \
  -e POSTGRES_PORT=5432 \
  -e POSTGRES_USER=retail_user \
  -e POSTGRES_PASSWORD=retail_password \
  -e POSTGRES_DB=retail_db \
  dbt run
```

### Lỗi 4: Redis cache cũ

```bash
# Xóa cache
docker-compose exec redis redis-cli FLUSHDB

# Hoặc restart redis
docker-compose restart redis
```

### Lỗi 5: CSV Import không chạy

```bash
# Kiểm tra Airflow DAG có được schedule không
curl http://localhost:8085/api/v1/dags/csv_daily_import/dagRuns

# Chạy thủ công
make csv-import

# Kiểm tra file có trong thư mục không
ls -la csv_input/

# Kiểm tra logs
docker-compose logs csv-watcher
```

### Lỗi 6: Disk full

```bash
# Dọn dẹp Docker
docker system prune -f
docker volume prune -f

# Xem dung lượng
docker system df
```

---

## 📞 Hỗ trợ

### Commands hữu ích (Makefile)

```bash
make up                 # Khởi động tất cả services
make down               # Dừng services
make restart            # Restart
make logs               # Xem logs
make csv-import         # Import CSV thủ công
make csv-process-full   # Import CSV + DBT transform
make dbt                # Chạy DBT
make ml                 # Train ML (Optuna 50 trials)
make ml-train-fast      # Train ML nhanh (no tuning)
make ml-predict         # Generate forecasts
make psql               # Vào PostgreSQL CLI
make clickhouse         # Vào ClickHouse CLI
```

### Kiểm tra nhanh

```bash
# Script kiểm tra health
docker-compose ps
docker-compose exec postgres pg_isready -U retail_user
docker-compose exec clickhouse clickhouse-client -q "SELECT 1"
curl http://localhost:8088/health
```

---

## 📄 License

MIT License

---

**Last Updated:** 2024-02-14
