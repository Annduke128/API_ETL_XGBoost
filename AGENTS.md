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

### 2 Môi trường Triển khai

Dự án hỗ trợ **2 cách triển khai** hoàn toàn khác nhau:

| Môi trường | Vị trí | Mục đích | Cách chạy |
|------------|--------|----------|-----------|
| **Development** | `docker/` | Local dev, testing | `make up` trong docker/ |
| **Production** | `k8s/` | K3s cluster, real deployment | GitHub Actions → K3s |

---

## 🏗️ Cấu trúc thư mục

```
Hasu_ML_k3s/
├── 📁 docker/                    # 🐳 DOCKER COMPOSE - Development
│   ├── docker-compose.yml        # Định nghĩa services
│   ├── Makefile                  # Commands cho Docker
│   ├── .env.example              # Template biến môi trường
│   ├── data_cleaning/            # Sync Tool Dockerfile
│   ├── dbt_retail/               # DBT Dockerfile
│   ├── ml_pipeline/              # ML Pipeline Dockerfile
│   └── README.md                 # Hướng dẫn Docker
│
├── 📁 k8s/                       # ☸️ KUBERNETES/K3s - Production
│   ├── 00-namespace/             # Namespace, Network Policies
│   ├── 01-storage/               # StorageClass, PVCs
│   ├── 02-config/                # ConfigMaps, Secrets
│   ├── 03-databases/             # PostgreSQL, ClickHouse, Redis
│   ├── 04-applications/          # Airflow, Superset
│   ├── 05-ml-pipeline/           # ML Jobs, CronJobs
│   ├── scripts/                  # Helper scripts
│   └── README.md                 # Hướng dẫn K3s
│
├── 📁 dbt_retail/                # DBT Project (shared)
│   ├── models/                   # Staging, Intermediate, Marts
│   ├── macros/                   # Custom SQL functions
│   ├── seeds/                    # Reference data
│   └── tests/                    # Data tests
│
├── 📁 ml_pipeline/               # ML Pipeline (shared)
│   ├── xgboost_forecast.py       # Main forecasting script
│   ├── train_models.py           # Training entry point
│   └── assets/                   # Email templates, logos
│
├── 📁 data_cleaning/             # ETL Scripts (shared)
│   ├── auto_process_csv.py       # Auto CSV processor
│   ├── csv_processor.py          # Core cleaning logic
│   └── sync_to_clickhouse.py     # PostgreSQL → ClickHouse sync
│
├── 📁 airflow/                   # Airflow DAGs
│   └── dags/
│       └── retail_pipeline_dag.py
│
├── 📁 csv_input/                 # CSV files (gitignored)
├── 📁 csv_output/                # Processed output
│
├── Makefile                      # Root Makefile (2 environments)
├── README.md                     # Main documentation
└── AGENTS.md                     # This file
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
| **Container** | Docker, Docker Compose | Dev environment |
| **Orchestration** | K3s, Kubernetes | Production deployment |
| **CI/CD** | GitHub Actions | Auto build & deploy |

---

## 🚀 Build và Run Commands

### 🐳 Development - Docker Compose

> Chạy trong thư mục `docker/`

```bash
cd docker

# Khởi động
make up                 # Infrastructure cơ bản
make up-ml              # Kèm ML Pipeline
make up-all             # Tất cả services

# Kiểm tra
make health             # Health check all
make status             # Xem container status
make logs               # Xem logs

# Data Pipeline
make sync-to-ch         # Sync PostgreSQL → ClickHouse
make dbt-build          # Build all DBT models
make dbt-test           # Run tests

# ML Pipeline
make ml                 # Train với Optuna (50 trials)
make ml-fast            # Train nhanh (no tuning)
make ml-optimal         # Train tối ưu (100 trials)
make ml-all             # Train + Predict + Email
make ml-predict         # Predict only

# Dừng/Dọn dẹp
make down               # Stop services
make down-v             # Stop + remove volumes
make clean              # Dọn Docker cache
```

### ☸️ Production - K3s

> Chạy từ root (yêu cầu kubectl connect đến K3s cluster)

```bash
# Deploy toàn bộ hệ thống
make k8s-deploy-all     # Deploy all K8s resources

# Chạy pipeline từng bước
make k3s-sync           # Chạy sync job
make k3s-dbt            # Chạy DBT build
make k3s-ml-train       # Train ML models
make k3s-ml-predict     # Generate predictions

# Hoặc chạy full pipeline
make app-k3s DOCKERHUB_USERNAME=yourusername

# Kiểm tra
make k8s-status         # Xem K8s status
make k8s-logs           # Xem logs

# Xóa
make k8s-delete         # Xóa namespace (⚠️ mất dữ liệu)
```

### 🔄 CI/CD - GitHub Actions

**Workflow files:**
- `.github/workflows/docker-build-push.yml` - Build & push images
- `.github/workflows/deploy-k3s-selfhosted.yml` - Deploy to K3s

**Triggers:**
- Push to `main` → Auto build & deploy
- Manual dispatch → `workflow_dispatch`

**Required Secrets:**
```yaml
DOCKERHUB_USERNAME      # Docker Hub username
DOCKERHUB_TOKEN         # Docker Hub access token
POSTGRES_PASSWORD       # PostgreSQL password
CLICKHOUSE_PASSWORD     # ClickHouse password
```

---

## 🔄 Luồng hoạt động

### Development (Docker)

```
Developer → Code Change → Local Test (docker) → Commit → Push
                                ↓
                    make up → make app → verify
```

### Production (K3s)

```
Developer → Push to main → GitHub Actions → Build Images
                                              ↓
                                         Push to Docker Hub
                                              ↓
                                    Self-Hosted Runner on K3s
                                              ↓
                                    Pull & Deploy to K3s
```

---

## 📊 Service Ports

### Docker (localhost)

| Service | Port | Mô tả |
|---------|------|-------|
| PostgreSQL | 5432 | OLTP Database |
| ClickHouse HTTP | 8123 | Data Warehouse |
| ClickHouse Native | 9000 | Data Warehouse |
| Redis | 6379 | Buffer & Cache |
| Airflow Web | 8085 | Workflow Scheduler |
| Superset | 8088 | BI Dashboard |

### K3s (NodePort)

| Service | NodePort | Mô tả |
|---------|----------|-------|
| Airflow | 30080 | Workflow Scheduler |
| Superset | 30088 | BI Dashboard |
| PostgreSQL | ClusterIP only | Dùng port-forward |
| ClickHouse | ClusterIP only | Dùng port-forward |

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
# Docker
cd docker && make dbt-test

# K3s
kubectl apply -f k8s/05-ml-pipeline/job-dbt-test.yaml -n hasu-ml
```

### Health Checks

```bash
# Docker
make health

# K3s
kubectl get pods -n hasu-ml
kubectl logs -n hasu-ml deployment/postgres
```

---

## 🔐 Security Considerations

### Docker (Development)

Default credentials (chỉ dùng cho dev):

| Service | Username | Password |
|---------|----------|----------|
| PostgreSQL | retail_user | retail_password |
| ClickHouse | default | clickhouse_password |
| Airflow | admin | admin |
| Superset | admin | admin |

> ⚠️ **WARNING**: Thay đổi mật khẩu mặc định trong `.env`!

### K3s (Production)

- Secrets được lưu trong GitHub Secrets
- Auto-inject vào Kubernetes Secrets qua GitHub Actions
- Không bao giờ commit secrets vào repo!

```bash
# Kiểm tra secrets trong K3s
kubectl get secrets -n hasu-ml
kubectl describe secret hasu-ml-secrets -n hasu-ml
```

---

## 📁 Key Configuration Files

| File | Mục đích | Environment |
|------|----------|-------------|
| `docker/.env` | Biến môi trường Docker | Dev |
| `docker/docker-compose.yml` | Định nghĩa services | Dev |
| `k8s/02-config/configmap.yaml` | K8s ConfigMap | Prod |
| `k8s/02-config/secrets-template.yaml` | Template secrets | Prod |
| `dbt_retail/dbt_project.yml` | Cấu hình DBT | Both |
| `dbt_retail/profiles.yml` | Kết nối database | Both |
| `.github/workflows/*.yml` | CI/CD pipelines | Prod |

---

## 🔍 Debugging và Troubleshooting

### Docker

```bash
cd docker

# Xem logs
make logs
make logs-ml-pipeline

# Reset dữ liệu
make reset-db           # Reset database (giữ CSV)
make reset-all          # Full reset (⚠️ xóa tất cả)

# Clean Docker
make clean
```

### K3s

```bash
# Xem logs
kubectl logs -f deployment/postgres -n hasu-ml
kubectl logs -f deployment/clickhouse -n hasu-ml

# Check events
kubectl get events -n hasu-ml --sort-by='.lastTimestamp'

# Pod không start
kubectl describe pod <pod-name> -n hasu-ml

# PVC pending
kubectl get pvc -n hasu-ml
kubectl describe pvc <pvc-name> -n hasu-ml

# Port forward để debug
kubectl port-forward svc/postgres 5432:5432 -n hasu-ml
kubectl port-forward svc/clickhouse 8123:8123 -n hasu-ml
```

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

### Quy trình làm việc

1. **Local Development**
   ```bash
   cd docker
   make up
   # Code changes
   make app  # Test full pipeline
   ```

2. **Test DBT changes**
   ```bash
   cd dbt_retail
   dbt deps
   dbt build --select staging,marts
   ```

3. **Test ML changes**
   ```bash
   cd docker
   make ml-fast  # Quick test
   ```

4. **Commit & Push**
   ```bash
   git add .
   git commit -m "feat: mô tả thay đổi"
   git push origin main
   ```

5. **GitHub Actions tự động deploy**
   - Build images
   - Push to Docker Hub
   - Deploy to K3s

---

## 🔐 Bảo Mật & Git Workflow

### .gitignore - Các File Được Bảo Vệ

| File/Pattern | Lý do |
|-------------|-------|
| `.env` | Chứa password, API keys |
| `k8s/02-config/secrets.yaml` | Secrets thực tế |
| `csv_input/*.csv` | Dữ liệu thô |
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

# 6. Push (CI/CD sẽ tự động chạy)
git push origin main
```

---

## 🧠 ML Pipeline Architecture

### Data Requirements & Lag Features

```
Training Data Requirements:
├── Minimum: 2 days (lag_1 only)
├── Recommended: 31+ days (lag_1, lag_7, lag_14, lag_30)
└── Optimal: 90+ days (full features + stable rolling stats)
```

| Lag Feature | Required Days | Created By |
|-------------|---------------|------------|
| `lag_1_quantity` | 2+ | `shift(1)` by (branch, product) |
| `lag_7_quantity` | 8+ | `shift(7)` by (branch, product) |
| `lag_14_quantity` | 15+ | `shift(14)` by (branch, product) |
| `lag_30_quantity` | 31+ | `shift(30)` by (branch, product) |

**Adaptive behavior:** Số lượng lag features tự động điều chỉnh dựa trên số ngày dữ liệu có sẵn.

### Data Validation Pipeline

```python
# 1. Load từ fct_regular_sales (không khuyến mại)
df = load_historical_data(days=0)

# 2. Validation: Chỉ giữ records có dữ liệu bán thực tế
df = df[df['daily_quantity'] > 0]
df = df[df['daily_revenue'] > 0]

# 3. Feature engineering với adaptive lag
df_features = create_features(df)
# → Tự động chọn lag features phù hợp

# 4. Training với TimeSeriesSplit
model = train_model(df_features, target='daily_quantity')
```

### Cold Start Handling

```python
if len(product_history) < 2:
    # Fallback: Category median + seasonal adjustment
    predicted_qty = category_median * seasonal_factor / 7
else:
    # Normal: XGBoost model prediction
    predicted_qty = model.predict(X)
```

| Mức độ dữ liệu | Số ngày | Phương pháp | Độ tin cậy |
|----------------|---------|-------------|------------|
| Cold start | < 2 | Category median | LOW |
| Warm up | 2-14 | Model với limited lags | MEDIUM |
| Stable | 14-30 | Full model features | HIGH |
| Mature | > 30 | Full model + all lags | HIGH |

### Batch Query Optimization

```python
# ❌ CŨ: N+1 Query (chậm)
for product in products:
    for branch in branches:
        query = f"SELECT * WHERE ma_hang = '{product}'"
        df = client.query(query)   # 3900 queries!

# ✅ MỚI: Batch Query (nhanh)
products = ['SP001', 'SP002', ...]
query = f"SELECT * WHERE ma_hang IN {products}"  # 1 query
history_df = client.query(query)
```

| Metric | Trước | Sau | Cải thiện |
|--------|-------|-----|-----------|
| Queries | ~3,900 | **2** | **~2000x** |
| Thờigian | 5-10 phút | **5-10 giây** | **~100x** |

### ABC-based Product Selection

```sql
CASE 
    WHEN cum_revenue_pct <= 0.8 THEN 'A'
    WHEN cum_revenue_pct <= 0.95 THEN 'B'
    ELSE 'C'
END as abc_class
```

### ML API Reference

```python
from ml_pipeline.xgboost_forecast import SalesForecaster

# Khởi tạo
forecaster = SalesForecaster(model_dir='/app/models')

# Training
metrics = forecaster.train_all_models(
    use_tuning=True,
    tuning_method='optuna',
    n_trials=50
)

# Prediction
forecasts = forecaster.predict_next_week(
    use_abc_filter=True,
    abc_top_n=5
)
```

---

## 📚 Tài liệu tham khảo

| File | Mô tả |
|------|-------|
| `README.md` | Tổng quan dự án, 2 cách triển khai |
| `docker/README.md` | Chi tiết Docker Compose |
| `k8s/README.md` | Chi tiết K3s deployment |
| `ARCHITECTURE.md` | Kiến trúc hệ thống và database |

---

## ⚠️ Lưu ý quan trọng cho Agents

### 1. Phân biệt 2 môi trường

| Tình huống | Hành động |
|------------|-----------|
| User chạy local/test | Làm việc trong `docker/` |
| User deploy production | Làm việc trong `k8s/` |
| User muốn CI/CD | Cập nhật `.github/workflows/` |

### 2. Docker Image Naming

```yaml
# Development
image: ml-pipeline:latest          # Build local

# Production  
image: ${DOCKERHUB_USERNAME}/hasu-ml-pipeline:latest  # Docker Hub
```

### 3. Path differences

| Context | Path |
|---------|------|
| Docker | `/app/models`, `/csv_input` |
| K8s | Cùng path nhưng dùng PVC mounts |

### 4. Secrets management

| Environment | Cách lưu |
|-------------|----------|
| Docker | `.env` file |
| K3s | GitHub Secrets → K8s Secrets |

---

---

## 🔥 PySpark ETL (Mới)

### Tổng quan

Hệ thống hỗ trợ **PySpark ETL** để xử lý song parallel các file Excel (Products, Inventory, Sales), tận dụng sức mạnh multi-core của Spark cluster.

### File PySpark ETL

```
spark-etl/python_etl/
├── import_products_spark.py      # Import DanhSachSanPham (parallel)
├── import_inventory_spark.py     # Import BaoCaoXuatNhapTon (parallel)
└── import_sales_spark.py         # Import BaoCaoBanHang (parallel)
```

### Cách Toggle PySpark/Pandas

```python
# data_cleaning/smart_processor.py line 20
USE_SPARK = True   # Dùng PySpark (song song)
USE_SPARK = False  # Dùng Pandas (đơn luồng)
```

### Ưu điểm PySpark

| Yếu tố | Pandas | PySpark | Cải thiện |
|--------|--------|---------|-----------|
| **Processing** | Single-thread | Multi-core | 3-5x faster |
| **Memory** | Load toàn bộ | Distributed | Không OOM |
| **Scalability** | 1 node | Cluster | Unlimited |
| **10K rows** | 5s | 2s | 2.5x |
| **100K rows** | 30s | 8s | 3.75x |
| **1M rows** | ❌ OOM | 45s | ∞ |

### Chạy PySpark ETL

```bash
# 1. Khởi động Spark cluster
cd docker && docker-compose --profile spark up -d

# 2. Ensure USE_SPARK = True trong smart_processor.py

# 3. Chạy pipeline
cd .. && make smart-process
```

### Build Docker Image

```bash
cd docker
docker-compose --profile spark build spark-etl
```

### Chi tiết kỹ thuật

- **Parallel Processing**: PySpark tự động phân chia data thành partitions, mỗi partition chạy song song trên 1 core
- **JDBC Parallel Write**: Ghi song song nhiều partitions vào PostgreSQL
- **Adaptive Query Execution**: Tự động optimize execution plan

### Khi nào dùng PySpark?

| Trường hợp | Khuyến nghị |
|------------|-------------|
| < 10K rows/ngày | Pandas (đơn giản) |
| 10K - 100K rows/ngày | PySpark (nhanh hơn) |
| > 100K rows/ngày | PySpark (bắt buộc) |
| Multiple files cùng lúc | PySpark (song song) |

### References

- Xem chi tiết: `PYSPARK_ETL_README.md`

---

### ML Pipeline Workflow Summary

```
┌──────────────────────────────────────────────────────────────┐
│                    ML PIPELINE WORKFLOW                       │
└──────────────────────────────────────────────────────────────┘

1. DATA LOADING (fct_regular_sales)
   ├── Query historical data (default: all days)
   ├── JOIN dim_product (category, brand, abc_class)
   └── JOIN int_dynamic_seasonal_factor (seasonal factors)

2. DATA VALIDATION
   ├── Filter: quantity > 0 AND revenue > 0
   ├── Check: unique days >= 2 (minimum for lag_1)
   ├── Check: time-series continuity
   └── Log: data quality metrics

3. FEATURE ENGINEERING (create_features)
   ├── Time-based: day_of_week, month, is_weekend, is_holiday
   ├── Lag features (adaptive):
   │   ├── lag_1:  requires >= 2 days
   │   ├── lag_7:  requires >= 8 days
   │   ├── lag_14: requires >= 15 days
   │   └── lag_30: requires >= 31 days
   ├── Rolling: mean/std 7, 14, 30 days
   ├── Seasonal: is_peak_day, seasonal_factor
   └── Categorical encoding: branch, category, brand

4. TRAINING (train_all_models)
   ├── Model 1: Product-level (MdAPE metric)
   │   └── Target: daily_quantity
   ├── Model 2: Category-level (MAPE metric)
   │   └── Target: aggregated category quantity
   └── Hyperparameter tuning: Optuna (default 50 trials)

5. PREDICTION (predict_next_week)
   ├── Select products (default: Top 50 ABC)
   ├── Load 60-day history (batch query)
   ├── For each product:
   │   ├── IF < 2 days history: cold start (category median)
   │   └── ELSE: XGBoost prediction
   └── Generate 7-day forecast

6. OUTPUT
   ├── Save to ClickHouse (ml_forecasts)
   ├── Save to PostgreSQL (ml_forecasts)
   ├── Export CSV (purchase_orders)
   └── Send email report
```

**Key Code Files:**
- `ml_pipeline/xgboost_forecast.py` - Main ML pipeline
- `ml_pipeline/email_notifier.py` - Email reporting

**Important Notes:**
- Lag features use pandas shift() grouped by (branch, product)
- Cold start threshold: < 2 days of history
- Training fails if < 2 days of data (not enough for lag_1)
- Always validate data quality before training

---

**Last Updated**: 2026-03-07 (Added ML workflow documentation)
