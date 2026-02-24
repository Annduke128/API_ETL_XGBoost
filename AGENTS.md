# AGENTS.md - Retail Data Pipeline

> File này chứa thông tin hướng dẫn dành cho AI coding agents làm việc với dự án Retail Data Pipeline.
> Ngôn ngữ chính trong dự án: **Tiếng Việt** (tài liệu, comments, tên biến có ý nghĩa)

---

## 📋 Tổng quan dự án

**Retail Data Pipeline** là hệ thống data pipeline hoàn chỉnh cho ngành bán lẻ, bao gồm:
- ETL tự động xử lý dữ liệu CSV
- Data Warehouse với PostgreSQL (OLTP) và ClickHouse (OLAP)
- BI Dashboard với Apache Superset
- ML Forecasting dự báo bán hàng sử dụng XGBoost

### Kiến trúc hệ thống

```
CSV Input ──▶ PostgreSQL (OLTP) ──▶ ClickHouse (DW) ──▶ BI/Analytics
     │              │                    │
     ▼              ▼                    ▼
 Data Cleaning   Transactions      Fact Tables
                 Products          Aggregations
                 Customers         Time-series
```

---

## 🏗️ Cấu trúc thư mục

```
retail_data_pipeline/
├── airflow/
│   ├── dags/
│   │   └── retail_pipeline_dag.py    # DAGs cho Airflow
│   └── plugins/                       # Plugins tùy chỉnh
├── config/                            # Cấu hình chung
├── csv_input/                         # Thư mục chứa CSV cần xử lý
│   ├── processed/                     # Đã xử lý
│   └── error/                         # Lỗi
├── csv_output/                        # Kết quả xử lý
├── data_cleaning/                     # Module làm sạch dữ liệu
│   ├── auto_process_csv.py           # Xử lý tự động
│   ├── csv_processor.py              # Class làm sạch chính
│   ├── csv_watcher.py                # Theo dõi file mới
│   ├── db_connectors.py              # Kết nối database
│   ├── redis_buffer.py               # Redis cache
│   ├── Dockerfile
│   └── requirements.txt
├── dbt_retail/                        # DBT project
│   ├── models/
│   │   ├── staging/                   # Làm sạch dữ liệu gốc
│   │   ├── intermediate/              # Transform trung gian
│   │   └── marts/                     # Facts & Dimensions
│   │       ├── core/                  # dim_date, dim_product, dim_branch
│   │       ├── sales/                 # fct_daily_sales, fct_monthly_sales
│   │       ├── inventory/             # fct_inventory_forecast_input
│   │       └── customers/             # fct_rfm_analysis
│   ├── macros/                        # Hàm tiện ích SQL
│   ├── seeds/                         # Dữ liệu tham chiếu
│   ├── tests/                         # DBT tests
│   ├── dbt_project.yml               # Cấu hình DBT
│   └── profiles.yml                   # Kết nối database
├── init/                              # Khởi tạo database
│   ├── clickhouse/
│   └── postgres/
├── ml_pipeline/                       # Machine Learning
│   ├── xgboost_forecast.py           # Dự báo XGBoost
│   ├── db_connectors.py              # Kết nối DB cho ML
│   ├── Dockerfile
│   └── requirements.txt
├── superset/                          # BI Configuration
│   ├── superset_config.py
│   ├── create_clickhouse_conn.py
│   └── docker-bootstrap.sh
├── .env                               # Environment variables
├── docker-compose.yml                 # Định nghĩa services
├── Makefile                          # Các lệnh thường dùng
├── README.md                          # Tài liệu ngườ i dùng
├── ARCHITECTURE.md                    # Kiến trúc chi tiết
└── QUICK_REFERENCE.md                 # Tham khảo nhanh
```

---

## 🛠️ Technology Stack

| Layer | Công nghệ | Mục đích |
|-------|-----------|----------|
| **Ingestion** | Python 3.11, Pandas | Xử lý CSV, làm sạch dữ liệu |
| **OLTP** | PostgreSQL 15 | Lưu trữ giao dịch thờigian thực |
| **OLAP/DW** | ClickHouse 24 | Phân tích dữ liệu lớn, time-series |
| **Cache/Buffer** | Redis 7 | Tạm thờ i, cache |
| **Transformation** | DBT 1.7 | Transform dữ liệu, data modeling |
| **Orchestration** | Apache Airflow 2.8 | Scheduling, workflow |
| **BI** | Apache Superset 2.1 | Dashboard, visualization |
| **ML** | XGBoost, Optuna, scikit-learn | Dự báo bán hàng + Hyperparameter tuning |
| **Container** | Docker, Docker Compose | Triển khai, quản lý services |

---

## 🚀 Build và Run Commands

### Khởi động hệ thống (sử dụng Makefile)

```bash
# Khởi động tất cả services
make up

# Kiểm tra health
make health

# Xem status
make status

# Dừng hệ thống
make down

# Restart
make restart
```

### Xử lý dữ liệu CSV

```bash
# Process CSV 1 lần (manual)
make csv-import

# Process CSV + chạy DBT transform
make csv-process-full

# Xóa dữ liệu đã xử lý
make csv-reset
```

**Lưu ý:** CSV import được schedule tự động trong Airflow DAG `csv_daily_import` chạy lúc 2h sáng mỗi ngày.

### DBT Commands

```bash
# Run tất cả models
make dbt

# Load seed data
make dbt-seed

# Run tests
make dbt-test

# Generate và serve docs (port 8080)
make dbt-docs
```

### ML Pipeline

```bash
# Train models với Optuna tuning (50 trials - default)
make ml
make ml-train

# Train nhanh (không tuning)
make ml-train-fast

# Train tối ưu (100 trials)
make ml-train-optimal

# Train + Generate forecasts
make ml-train-predict

# Generate predictions từ model đã train
make ml-predict
```

### Database CLI

```bash
# PostgreSQL
make psql

# ClickHouse
make clickhouse


# Redis
make redis
```

---

## 📊 Service Ports

| Service | Port | Mô tả |
|---------|------|-------|
| PostgreSQL | 5432 | OLTP Database |
| ClickHouse HTTP | 8123 | Data Warehouse (HTTP) |
| ClickHouse Native | 9000 | Data Warehouse (Native) |
| Redis | 6379 | Buffer & Cache |
| Airflow Web | 8085 | Workflow Scheduler UI |
| Superset | 8088 | BI Dashboard |
| DBT Docs | 8080 | Documentation (khi chạy) |

---

## 🔧 Code Style Guidelines

### Python

- **Tiếng Việt**: Comments và docstrings viết bằng tiếng Việt
- **Snake_case**: Tên biến, hàm (`ma_giao_dich`, `tong_doanh_thu`)
- **Class names**: PascalCase (`RetailDataCleaner`, `SalesForecaster`)
- **Constants**: UPPER_CASE (`COLUMNS_SCHEMA`, `COLUMN_MAPPING`)
- **Type hints**: Sử dụng typing (`def clean(self, file_path: str) -> pd.DataFrame:`)
- **Logging**: Sử dụng module logging thay vì print

### SQL (DBT)

- **Lowercase**: Từ khóa SQL viết thường (`select`, `from`, `where`)
- **Snake_case**: Tên cột, bảng
- **Tiếng Việt**: Tên cột gốc từ dữ liệu CSV (vd: `ma_giao_dich`, `ten_hang`)
- **Models**: Tổ chức theo layer (`staging/`, `intermediate/`, `marts/`)
- **Tests**: Thêm tests cho primary keys, relationships, not_null

### File Organization

```
models/
├── staging/           # Views, làm sạch cơ bản
├── intermediate/      # Ephemeral, logic trung gian
└── marts/            # Tables, dữ liệu cuối cùng
    ├── core/         # Dimensions
    ├── sales/        # Sales facts
    ├── inventory/    # Inventory facts
    └── customers/    # Customer analytics
```

---

## 🧪 Testing Strategy

### DBT Tests

Các tests tích hợp trong `sources.yml` và `schema.yml`:

```yaml
columns:
  - name: id
    tests:
      - unique
      - not_null
  - name: ma_hang
    tests:
      - relationships:
          to: source('retail_source', 'products')
          field: id
```

Chạy tests:
```bash
make dbt-test
```

### Health Checks

```bash
# Tất cả services
make health

# Từng service
make health-postgres
make health-clickhouse
make health-redis
make health-superset
```

---

## 🔐 Security Considerations

### Default Credentials (Development Only)

> ⚠️ **WARNING**: Thay đổi mật khẩu mặc định trước khi deploy production!

| Service | Username | Password |
|---------|----------|----------|
| PostgreSQL | retail_user | retail_password |
| ClickHouse | default | clickhouse_password |

| Airflow | admin | admin |
| Superset | admin | admin |

### Environment Variables

Các biến môi trường được định nghĩa trong `.env`:

```bash
# Database connections
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=retail_db
POSTGRES_USER=retail_user
POSTGRES_PASSWORD=retail_password

# ClickHouse
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=9000
CLICKHOUSE_DB=retail_dw
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=clickhouse_password
```

---

## 📁 Key Configuration Files

| File | Mục đích |
|------|----------|
| `docker-compose.yml` | Định nghĩa tất cả Docker services |
| `Makefile` | Tự động hóa các lệnh thường dùng |
| `.env` | Biến môi trường |
| `dbt_retail/dbt_project.yml` | Cấu hình DBT project |
| `dbt_retail/profiles.yml` | Kết nối database cho DBT |
| `dbt_retail/packages.yml` | Dependencies DBT packages |
| `superset/superset_config.py` | Cấu hình Superset |

---

## 🔍 Debugging và Troubleshooting

### Xem logs

```bash
# Tất cả services
make logs

# Specific service
docker-compose logs -f postgres
docker-compose logs -f clickhouse
docker-compose logs -f airflow-webserver
```

### Reset dữ liệu

```bash
# Reset database (giữ CSV files)
make reset-db

# Full reset (⚠️ xóa tất cả data)
make reset-all
```

### Clean Docker

```bash
make clean
# Hoặc thủ công:
docker system prune -f
docker volume prune -f
```

### Common Issues

1. **Port đã được sử dụng**: Kiểm tra `sudo lsof -i :5432`
2. **Container unhealthy**: `docker-compose restart <service>`
3. **DBT connection refused**: Kiểm tra `POSTGRES_HOST` environment variable
4. **Redis cache cũ**: `docker-compose exec redis redis-cli FLUSHDB`

---

## 📝 Database Schema

### PostgreSQL (OLTP)

- `branches` - Chi nhánh
- `products` - Sản phẩm
- `transactions` - Giao dịch header
- `transaction_details` - Chi tiết giao dịch
- `ml_forecasts` - Kết quả dự báo ML

### ClickHouse (DW)

- `fact_transactions` - Fact table chính
- `agg_daily_sales` - Aggregated materialized view

---

## 🤝 Development Workflow

1. **Thay đổi code** → Test locally
2. **Chạy DBT** → `make dbt`
3. **Chạy tests** → `make dbt-test`
4. **Kiểm tra health** → `make health`
5. **Commit changes**

---

## 📚 Tài liệu tham khảo

- `README.md` - Hướng dẫn chi tiết ngườ i dùng
- `ARCHITECTURE.md` - Kiến trúc hệ thống và database
- `QUICK_REFERENCE.md` - Cheat sheet commands

---

---

## 🔐 Bảo Mật & Git Workflow

### .gitignore - Các File Được Bảo Vệ

| File/Pattern | Lý do |
|-------------|-------|
| `.env` | Chứa password, API keys |
| `csv_input/*.csv` | Dữ liệu thô, không commit |
| `*.pkl`, `*.joblib` | ML models (lớn, tái tạo được) |
| `ml_pipeline/email_config.yaml` | Email cá nhân |
| `__pycache__/` | Python cache |
| `dbt_retail/target/` | Build artifacts |

### Push Code Lên GitHub

```bash
# 1. Kiểm tra file thay đổi
git status

# 2. Xem chi tiết thay đổi
git diff

# 3. Add file (tự động ignore file trong .gitignore)
git add .

# 4. Kiểm tra lại trước khi commit
git diff --cached --name-only

# 5. Commit
git commit -m "feat: Mô tả thay đổi"

# 6. Push (cần cấu hình token/SSH)
git push origin main
```

Xem chi tiết trong `GIT_COMMIT_GUIDE.md`

---

**Last Updated**: 2024-02-14

---

## 🧠 ML Pipeline Architecture

### Batch Query Optimization

Hệ thống ML đã được tối ưu để tránh N+1 query problem:

```python
# ❌ CŨ: N+1 Query (chậm)
for product in products:           # ~1300 lần
    for branch in branches:        # ~3 lần
        query = f"SELECT * WHERE ma_hang = '{product}'"
        df = client.query(query)   # 3900 queries!

# ✅ MỚI: Batch Query (nhanh)
products = ['SP001', 'SP002', ...]  # Top 15 ABC
query = f"SELECT * WHERE ma_hang IN {products}"  # 1 query
history_df = client.query(query)
# Xử lý trong memory với pandas groupby
```

| Metric | Trước | Sau | Cải thiện |
|--------|-------|-----|-----------|
| Queries | ~3,900 | **2** | **~2000x** |
| Thờigian | 5-10 phút | **5-10 giây** | **~100x** |

### ABC-based Product Selection

ML prediction chỉ tập trung vào sản phẩm có giá trị cao:

```sql
-- Logic: Phân loại ABC trong DBT (int_product_performance.sql)
CASE 
    WHEN cum_revenue_pct <= 0.8 THEN 'A'  -- Top 80% doanh thu
    WHEN cum_revenue_pct <= 0.95 THEN 'B' -- 80-95% doanh thu
    ELSE 'C'                               -- 95-100% doanh thu
END as abc_class
```

| Class | Số lượng | % Doanh thu | ML Action |
|-------|----------|-------------|-----------|
| A | Top 5 | ~80% | Dự báo chi tiết |
| B | Top 5 | ~15% | Dự báo chi tiết |
| C | Top 5 | ~5% | Dự báo chi tiết |
| Khác | ~1,285 | ~0% | Bỏ qua / Ước tính |

### Adaptive Features

Tự động điều chỉnh features dựa trên số ngày dữ liệu có sẵn:

```python
def create_features(self, df):
    n_days = df['ngay'].nunique()
    
    # Chọn lag phù hợp với dữ liệu
    if n_days >= 30:
        available_lags = [1, 7, 14, 30]
    elif n_days >= 14:
        available_lags = [1, 7, 14]
    elif n_days >= 7:
        available_lags = [1, 7]
    else:
        available_lags = [1]
    
    # Tạo lag features
    for lag in available_lags:
        df[f'lag_{lag}_quantity'] = df.groupby(['chi_nhanh', 'ma_hang'])['daily_quantity'].shift(lag)
```

### ML API Reference

```python
from ml_pipeline.xgboost_forecast import SalesForecaster

# Khởi tạo
forecaster = SalesForecaster(model_dir='/app/models')

# Training với Optuna tuning
metrics = forecaster.train_all_models(
    use_tuning=True,
    tuning_method='optuna',
    n_trials=50,
    days=365
)

# Prediction với ABC filter (mặc định)
forecasts = forecaster.predict_next_week(
    use_abc_filter=True,   # Chỉ dự báo Top 15 ABC
    abc_top_n=5            # Top 5 từ mỗi loại
)

# Prediction tất cả sản phẩm (chậm)
forecasts = forecaster.predict_next_week(use_abc_filter=False)
```
