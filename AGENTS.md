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
| ClickHouse HTTP | 8123 | Data Warehouse (HTTP - optional) |
| ClickHouse Native | **9000** | Data Warehouse (Native Protocol) |
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
kubectl port-forward svc/clickhouse 9000:9000 -n hasu-ml  # Native protocol
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
├── Minimum: 2 days (technical minimum for lag_1)
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
| Cold start | < 2 | Category median (Model 2) | LOW |
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

## 🔥 Python ETL Pipeline

### Tổng quan

ETL Pipeline sử dụng **Python + PySpark** để xử lý dữ liệu CSV/Excel, ghi vào PostgreSQL (OLTP), sau đó đồng bộ lên ClickHouse (OLAP/DW).

### Kiến trúc ETL

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   CSV/Excel     │────▶│   Python ETL     │────▶│   PostgreSQL    │
│   Input Files   │     │   (PySpark)      │     │   (OLTP)        │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
         │                                                │
         │          ┌──────────────────────┐              │
         │          │   Column Mapping     │              │
         │          │   - ĐVT→don_vi_tinh  │              │
         │          │   - Mã hàng→ma_hang  │              │
         └─────────▶│   - Thờigian→ngay    │◄─────────────┘
                    └──────────────────────┘              │
                                                          ▼
                                                  ┌─────────────────┐
                                                  │   ClickHouse    │
                                                  │   (OLAP/DW)     │
                                                  └─────────────────┘
```

### File ETL chính

```
spark-etl/python_etl/
├── etl_main.py              # Main ETL script (sử dụng hiện tại)
├── import_products.py       # Import DanhSachSanPham
└── sync_to_clickhouse.py    # Sync PostgreSQL → ClickHouse
```

### Luồng xử lý

| Bước | File nguồn | Xử lý | Đích |
|------|-----------|-------|------|
| 1 | `DanhSachSanPham*.csv` | Parse nhóm hàng 3 cấp, mapping cột | PostgreSQL `products` |
| 2 | `BaoCaoBanHang*.xlsx` | Trích xuất giao dịch, chi tiết | PostgreSQL `transactions` + `transaction_details` |
| 3 | PostgreSQL tables | Type casting, NULL handling | ClickHouse staging tables |

### Column Mapping

| CSV Column | DB Column | Ghi chú |
|------------|-----------|---------|
| Mã hàng | ma_hang | Primary key |
| Tên hàng | ten_hang | Product name |
| Nhóm hàng(3 Cấp) | cap_1, cap_2, cap_3 | Parse từ chuỗi |
| ĐVT | don_vi_tinh | Đơn vị tính |
| Mã giao dịch | ma_giao_dich | Transaction ID |
| Thờigian | ngay | Date |
| SL | so_luong | Quantity |
| Giá bán/SP | don_gia | Unit price |
| Chi nhánh | ma_chi_nhanh | Branch code |

### Commands

**K3s:**
```bash
# Chạy ETL
make k3s-spark-etl      # Chạy ETL job
make k3s-spark          # Interactive mode

# Xem logs
kubectl logs -n hasu-ml job/spark-etl -f

# Full pipeline
make app-k3s            # ETL → DBT → ML
```

**Docker (Development):**
```bash
cd docker
make sync-to-ch         # Sync PostgreSQL → ClickHouse
```

### Performance

| Dataset | Records | Thờigian |
|---------|---------|----------|
| Products | ~16,000 | ~2s |
| Transactions | ~7,500 | ~3s |
| Transaction Details | ~16,000 | ~3s |
| **Total** | **~40,000** | **~5-10s** |

### Docker Image

```bash
# Image hiện tại
docker pull annduke/hasu-spark-etl:real-final

# Build lại (nếu cần)
cd spark-etl
docker build -t hasu-spark-etl:latest .
```

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
   │   ├── lag_1:  requires >= 2 days (technical minimum)
   │   ├── lag_7:  requires >= 8 days
   │   ├── lag_14: requires >= 15 days
   │   └── lag_30: requires >= 31 days
   ├── Rolling: mean/std 7, 14, 30 days
   ├── Seasonal: is_peak_day, seasonal_factor
   └── Categorical encoding: branch, category, brand

4. TRAINING (train_all_models) - Luôn dùng Optuna tuning
   ├── Model 1: Product-level (MdAPE primary)
   │   ├── Target: daily_quantity
   │   └── Metrics: MAE, MdAPE, MAPE (validation)
   ├── Model 2: Category-level (MAPE primary)
   │   ├── Target: aggregated category quantity
   │   └── Metrics: MAE, MdAPE, MAPE (validation)
   └── Hyperparameter tuning: Optuna (default 50 trials)
       └── Objective: MdAPE (Model 1) / MAPE (Model 2)

5. PREDICTION (predict_next_week)
   ├── Select products (default: Top 50 ABC)
   ├── Load 60-day history (batch query)
   ├── For each product:
   │   ├── IF < 14 days history: cold start (category median)
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
- Cold start threshold: < 2 days of history (use category-level Model 2)
- Product-level training: ALL products (no minimum day filter)
- Always validate data quality before training

### ML Metrics - Chiến lược đa góc nhìn

Hệ thống sử dụng **3 metrics** để đánh giá toàn diện:

| Metric | Công thức | Ý nghĩa | Khi nào dùng |
|--------|-----------|---------|--------------|
| **MAE** | mean(\|actual - predicted\|) | Trung bình dư/thiếu mỗi ngày (đơn vị) | Biết chính xác kho bị thiếu bao nhiêu |
| **MdAPE** | median(\|error/actual\|) × 100% | 50% ngày sai số dưới ngưỡng này | Phát hiện ngày sai số đột biến (Model 1) |
| **MAPE** | mean(\|error/actual\|) × 100% | Sai số % trung bình | Đánh giá tổng thể (Model 2) |

**Chiến lược tối ưu:**
- **Model 1 (Product)**: Tối ưu MdAPE (robust với outliers của từng sản phẩm)
- **Model 2 (Category)**: Tối ưu MAPE (đánh giá tổng thể category)
- **Validation**: Log đầy đủ MAE, MdAPE, MAPE để có cái nhìn đa chiều

**Ví dụ output:**
```
📊 Validation Metrics:
   📏 MAE:   12.35      ← Trung bình mỗi ngày kho bị dư/thiếu (đơn vị)
   📈 MAPE:  15.73%     ← Sai số % trung bình
   📉 MdAPE: 6.21%      ← 50% ngày sai số dưới ngưỡng này
   📐 RMSE:  18.90
```

---

**Last Updated**: 2026-03-18 (Refactored: removed train_model without tuning, unified to Optuna only; MdAPE for Model 1, MAPE for Model 2)

---

## 🆕 Cập nhật mới nhất (2026-03-18)

### 1. ML Pipeline Refactoring - Unified Optuna Training ⭐

**Thay đổi:** Đơn giản hóa ML pipeline bằng cách **loại bỏ `train_model()` không tuning**, chỉ giữ `train_model_optuna()`

**Lý do:**
- Đảm bảo tính nhất quán: Luôn dùng hyperparameter tuning
- Giảm complexity: Không cần maintain 2 code paths
- Chính xác hơn: Optuna tìm được params tốt hơn default

**Thay đổi chi tiết:**
```python
# ❌ CŨ: 2 hàm training
- train_model()           # Default params, no tuning
- train_model_optuna()    # Bayesian optimization

# ✅ MỚI: Chỉ 1 hàm
train_model_optuna()      # Luôn tuning, fallback giảm n_trials khi ít data
```

**Metric Strategy:**
| Model | Primary Metric | Mục đích |
|-------|---------------|----------|
| Model 1 (Product) | **MdAPE** | Robust với outliers của từng sản phẩm |
| Model 2 (Category) | **MAPE** | Đánh giá tổng thể category trend |

**Breaking Changes:**
- `train_all_models(use_tuning=True/False)` → Bỏ parameter, luôn tuning
- `train_all_models(tuning_method='optuna')` → Giữ lại để chọn method

---

## 🗂️ Cập nhật trước (2026-03-16)

### 1. Inventory Import trực tiếp ClickHouse

**Thay đổi:** File `BaoCaoXuatNhapTon_*.xlsx` được import **trực tiếp** vào ClickHouse (bypass PostgreSQL)

```python
# Trong etl_main.py - process_inventory_pyspark()
- Đọc file Excel
- Transform columns  
- Ghi trực tiếp vào ClickHouse.staging_inventory_transactions
```

**Lý do:** Inventory là dữ liệu phân tích, không cần ACID transactions của PostgreSQL

### 2. Cột Quy đổi (quy_doi)

**Thay đổi:** Thêm cột `quy_doi` từ Excel vào bảng `products`

| Mã hàng | Tên | quy_doi | Ý nghĩa |
|---------|-----|---------|---------|
| 16000109 | Cốc giấy đỏ | 1 | Đơn vị lẻ |
| 16000109-1 | Cốc giấy đỏ | 50 | Lốc 50 cái |
| 16000109-2 | Cốc giấy đỏ | 1200 | Thùng 1200 cái |

### 3. Purchase Order Generation ⭐ CẬP NHẬT 2026-03-18

**Thay đổi:** Cập nhật hàm `generate_purchase_order_csv()` với **Safety Stock**

**Công thức Tồn kho an toàn (Safety Stock):**
```
Safety Stock = (Nhu cầu cao nhất × Lead time max) - (Nhu cầu TB × Lead time TB)

Trong đó:
- Nhu cầu cao nhất: Max daily demand (28 ngày gần nhất)
- Nhu cầu TB: Average daily demand (28 ngày gần nhất)
- Lead time max: Thờigian giao hàng tối đa (mặc định: 7 ngày)
- Lead time TB: Thờigian giao hàng trung bình (mặc định: 5 ngày)
```

**Công thức Lượng cần nhập (cập nhật):**
```
Lượng cần nhập = MAX(Dự báo 7 ngày, Tồn kho tối ưu + Safety Stock) - Tồn kho hiện tại

Trong đó:
- Tồn kho tối ưu = median(lượng bán tuần + tồn nhỏ nhất × 0.75) qua 4 tuần
- Safety Stock = (Nhu cầu max × Lead time max) - (Nhu cầu TB × Lead time TB)
```

**Tham số:**
| Tham số | Mặc định | Mô tả |
|---------|----------|-------|
| `lead_time_max` | 7 | Lead time tối đa (ngày) |
| `lead_time_avg` | 5 | Lead time trung bình (ngày) |
| `top_n` | 50 | Số sản phẩm cần đặt |

**Ví dụ sử dụng:**
```python
# Với lead time mặc định
forecaster.generate_purchase_order_csv()

# Với lead time tùy chỉnh
forecaster.generate_purchase_order_csv(lead_time_max=10, lead_time_avg=6)
```

**Output CSV - Các cột mới:**
| Cột | Mô tả |
|-----|-------|
| `ton_an_toan` | Tồn kho an toàn (Safety Stock) |
| `tong_muc_tieu` | Tổng mục tiêu = Tối ưu + An toàn |
| `ton_kho_toi_uu` | Tồn kho tối ưu (công thức cũ) |
| `luong_can_nhap` | Lượng cần nhập (theo công thức mới) |

### 4. Docker Images mới

| Image | Tag | Thay đổi |
|-------|-----|----------|
| annduke/hasu-spark-etl | real-final-v18 | + inventory import, + quy_doi |
| annduke/hasu-ml-pipeline | latest | + purchase order generation |

### 5. Schema Updates

**PostgreSQL:**
```sql
ALTER TABLE products ADD COLUMN quy_doi INTEGER DEFAULT 1;
```

**ClickHouse:**
```sql
CREATE TABLE staging_inventory_transactions (...)
ENGINE = MergeTree()
ORDER BY (snapshot_date, ma_hang, chi_nhanh);
```

---

## 🐛 ML Pipeline Troubleshooting

### Issue 1: ClickHouse Connection EOFError

**Symptom:**
```
EOFError: Unexpected EOF while reading bytes
```

**Root Cause:** 
- ConfigMap has `CLICKHOUSE_PORT=8123` (HTTP port)
- But `clickhouse-driver` library requires port `9000` (native protocol)

**Fix:**
```bash
kubectl patch configmap -n hasu-ml hasu-ml-config \
  --type merge -p '{"data":{"CLICKHOUSE_PORT":"9000"}}'
```

> **✅ RESOLVED**: All components now use native driver with port 9000 by default.

### Issue 2: Query Error - sf.updated_at not found

**Symptom:**
```
DB::Exception: Identifier 'sf.updated_at' cannot be resolved from table with name sf
```

**Root Cause:**
- Table `int_dynamic_seasonal_factor` has column `calculated_at`, not `updated_at`

**Fix:**
In `ml_pipeline/xgboost_forecast.py`, replace all `sf.updated_at` with `sf.calculated_at` (21 occurrences).

### Issue 3: Missing ml_forecasts Table

**Symptom:**
```
psycopg2.errors.UndefinedTable: relation "ml_forecasts" does not exist
```

**Fix:**
```sql
CREATE TABLE IF NOT EXISTS ml_forecasts (
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
```

---

## 🆕 Cập nhật mới nhất (2026-03-18)

### 6. ML Pipeline - Bổ sung WMAPE Metric ⭐

**Thay đổi:** Thêm chỉ số **WMAPE (Weighted Mean Absolute Percentage Error)** vào hệ thống đánh giá model

**Chiến lược đa góc nhìn:**

```
┌─────────────────────────────────────────────────────────────┐
│           CHIẾN LƯỢC ĐÁNH GIÁ ĐA GÓC NHÌN                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Tối ưu (Optuna Objective)                               │
│     └── Log-Transform + MSE                                 │
│         → Hội tụ mượt mà, tự động khắc phục outliers        │
│                                                             │
│  2. Đánh giá (Validation/Reporting)                         │
│     └── In cả 3 chỉ số:                                     │
│         ├── MAE    → Trung bình dư/thiếu (đơn vị)          │
│         ├── WMAPE  → Sai số % tổng thể (an toàn nhất)      │
│         └── MdAPE  → 50% ngày sai số dưới ngưỡng này       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Các chỉ số được tính:**

| Metric | Công thức | Ý nghĩa | Ngưỡng tốt |
|--------|-----------|---------|------------|
| **MAE** | mean(\|y - ŷ\|) | Trung bình mỗi ngày kho bị dư/thiếu bao nhiêu đơn vị | < 15 |
| **WMAPE** | Σ\|y - ŷ\| / Σy × 100% | Sai số phần trăm tổng thể, không bị outliers ảnh hưởng | < 20% |
| **MdAPE** | median(\|y - ŷ\|/y) × 100% | 50% ngày có sai số dưới ngưỡng này | < 15% |
| **MAPE** | mean(\|y - ŷ\|/y) × 100% | Tham khảo (có thể bị outliers ảnh hưởng) | < 20% |

**Code changes:**
- `xgboost_forecast.py`: Thêm hàm `weighted_mean_absolute_percentage_error()`
- `train_model()`: Tính cả 4 metrics (MAE, WMAPE, MdAPE, MAPE) trong CV
- `train_model_optuna()`: Log cả 3 chỉ số chính sau validation
- `train_all_models()`: Training summary hiển thị đầy đủ metrics

**Ví dụ output mới:**
```python
📊 VALIDATION METRICS (3 chỉ số đa góc nhìn):
   📏 MAE:    12.3456    ← Trung bình mỗi ngày kho bị dư/thiếu (đơn vị)
   📊 WMAPE:  8.52%      ← Sai số phần trăm tổng thể (an toàn nhất)
   📈 MdAPE:  6.21%      ← 50% ngày sai số dưới ngưỡng này
   📉 MAPE:   15.73%     ← Tham khảo (có thể bị outliers ảnh hưởng)
   📉 RMSE:   18.9012    ← Sai số bình phương trung bình
   
💡 Giải thích:
   → MAE: Dự báo sai bao nhiêu đơn vị mỗi ngày
   → WMAPE: Sai số % tổng thể, dùng cho inventory planning
   → MdAPE: 50% ngày có sai số dưới 6.21%
```

> ⚠️ **UPDATE 2026-03-18**: WMAPE đã bị **loại bỏ** và `train_model()` (không tuning) cũng bị xóa. 
> Xem [ML Pipeline Refactoring](#1-ml-pipeline-refactoring---unified-optuna-training-) ở trên.

---

### 7. Purchase Order - Safety Stock ⭐ MỚI

**Thay đổi:** Cập nhật `generate_purchase_order_csv()` với **Tồn kho an toàn (Safety Stock)**

**Công thức Safety Stock:**
```
Safety Stock = (Nhu cầu cao nhất × Lead time max) - (Nhu cầu TB × Lead time TB)

Trong đó:
- Nhu cầu cao nhất: Max daily demand (28 ngày gần nhất)
- Nhu cầu TB: Average daily demand (28 ngày gần nhất)
- Lead time max: Thờigian giao hàng tối đa (mặc định: 7 ngày)
- Lead time TB: Thờigian giao hàng trung bình (mặc định: 5 ngày)
```

**Công thức Lượng cần nhập (cập nhật):**
```
Lượng cần nhập = MAX(Dự báo 7 ngày, Tồn kho tối ưu + Safety Stock) - Tồn kho hiện tại
```

**Tham số:**
| Tham số | Mặc định | Mô tả |
|---------|----------|-------|
| `lead_time_max` | 7 | Lead time tối đa (ngày) |
| `lead_time_avg` | 5 | Lead time trung bình (ngày) |

**Ví dụ sử dụng:**
```python
# Với lead time mặc định (7 và 5 ngày)
forecaster.generate_purchase_order_csv()

# Với lead time tùy chỉnh (10 và 6 ngày)
forecaster.generate_purchase_order_csv(lead_time_max=10, lead_time_avg=6)
```

**Output CSV - Các cột mới:**
- `ton_an_toan`: Tồn kho an toàn (Safety Stock)
- `tong_muc_tieu`: Tổng mục tiêu = Tối ưu + An toàn
- `luong_can_nhap`: Lượng cần nhập (theo công thức mới)

---

### 8. Fix Query "Bán Tuần Trước" - ISO Week ⭐

**Thay đổi:** Query dữ liệu bán tuần trước theo **ISO Week** thay vì ngày

**Vấn đề cũ:**
- Dùng `today() - 14` đến `today() - 7` để lấy tuần trước
- Nếu dữ liệu chậm hoặc hôm nay là giữa tuần → lấy sai dữ liệu

**Giải pháp mới:**
```sql
-- Lấy tuần hiện tại từ dữ liệu
SELECT 
    toWeek(MAX(transaction_date)) as current_week,
    toYear(MAX(transaction_date)) as current_year
FROM retail_dw.fct_regular_sales

-- Query tuần trước (đầy đủ từ thứ 2 đến chủ nhật)
SELECT 
    f.product_code as ma_hang,
    SUM(f.quantity_sold) as last_week_sales
FROM retail_dw.fct_regular_sales f
WHERE f.product_code IN ('...')
  AND toYear(f.transaction_date) = {last_year}
  AND toWeek(f.transaction_date) = {last_week}
GROUP BY f.product_code
```

**Xử lý đặc biệt:**
- Tuần 1 năm mới → Tuần 52 năm trước
- Luôn lấy đủ 7 ngày (thứ 2 đến chủ nhật) của tuần trước

---

**Last Updated**: 2026-03-18 (Refactored ML Pipeline: removed train_model without tuning, unified to Optuna only; MdAPE for Model 1, MAPE for Model 2)
