# Retail Data Pipeline - Hệ thống Data Warehouse cho ngành bán lẻ

Hệ thống data pipeline hoàn chỉnh với ETL tự động, Data Warehouse, BI Dashboard và ML Forecasting.

**🌐 Ngôn ngữ**: Tiếng Việt (tài liệu, comments, tên biến có ý nghĩa)

---

## 📋 Mục lục

1. [Tổng quan](#tổng-quan)
2. [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
3. [Triển khai](#triển-khai)
   - [Cách 1: Docker Compose (Dev/Test)](#cách-1-docker-compose-devtest)
   - [Cách 2: K3s Cluster + GitHub Actions (Production)](#cách-2-k3s-cluster--github-actions-production)
4. [So sánh 2 cách triển khai](#so-sánh-2-cách-triển-khai)
5. [Kiểm tra healthcheck](#kiểm-tra-healthcheck)
6. [Import dữ liệu CSV](#import-dữ-liệu-csv)
7. [Chạy DBT Project](#chạy-dbt-project)
8. [Chạy ML Models](#chạy-ml-models)
9. [Airflow Workflow](#-airflow-workflow-orchestration)
10. [Kết nối Superset BI](#kết-nối-superset-bi)
10. [Troubleshooting](#troubleshooting)

---

## 🎯 Tổng quan

Dự án cung cấp **2 cách triển khai** phù hợp với từng môi trường:

| Môi trường | Phương pháp | Mục đích | Độ phức tạp |
|------------|-------------|----------|-------------|
| **Development / Testing** | Docker Compose | Test local, phát triển tính năng | ⭐ Thấp |
| **Production / Staging** | K3s + GitHub Actions | Deploy thực tế, auto-scaling, CI/CD | ⭐⭐⭐ Cao |

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
| **Airflow** | 8085 / 30080 (K3s) | Workflow Scheduler |
| **Superset** | 8088 / 30088 (K3s) | BI Dashboard |

---

## 🚀 Triển khai

### Cách 1: Docker Compose (Dev/Test)

> **Phù hợp**: Phát triển tính năng, test local, demo nhanh

#### Yêu cầu hệ thống

| Resource | Tối thiểu | Khuyến nghị |
|----------|-----------|-------------|
| RAM | 8GB | 16GB+ |
| Disk | 20GB free | 50GB+ SSD |
| Docker | 24.0+ | Latest |
| Docker Compose | 2.20+ | Latest |

#### Các bước triển khai

```bash
# 1. Vào thư mục docker
cd docker

# 2. Copy file môi trường
cp .env.example .env
# (Sửa các giá trị trong .env nếu cần)

# 3. Khởi động hệ thống
make up           # Infrastructure cơ bản
make up-ml        # Hoặc: Kèm ML Pipeline
make up-all       # Hoặc: Tất cả services

# 4. Kiểm tra status
make status
make health
```

#### Commands thường dùng (Docker)

```bash
cd docker

# Xem tất cả commands
make help

# Data Pipeline
make sync-to-ch        # Sync PostgreSQL → ClickHouse
make dbt-build         # Build all models
make ml                # Train ML models
make ml-all            # Train + Predict + Email

# Database CLI
make psql              # PostgreSQL CLI
make clickhouse        # ClickHouse CLI
make redis             # Redis CLI

# Maintenance
make down              # Stop services
make down-v            # Stop + remove volumes
make clean             # Dọn Docker cache
```

📖 **Xem chi tiết**: [docker/README.md](docker/README.md)

---

### Cách 2: K3s Cluster + GitHub Actions (Production)

> **Phù hợp**: Deploy thực tế, production, auto-scaling, CI/CD tự động

#### Kiến trúc triển khai

```
┌─────────────────────────────────────────────────────────────────┐
│                    GitHub Repository                             │
│  ┌─────────────┐    ┌──────────────────────────────────────┐   │
│  │   Code      │───▶│  GitHub Actions                      │   │
│  │   Push      │    │  ┌─────────────┐  ┌──────────────┐   │   │
│  └─────────────┘    │  │ Build Images│─▶│ Push Docker  │   │   │
│                     │  │ (3 images)  │  │ Hub          │   │   │
│                     │  └─────────────┘  └──────────────┘   │   │
│                     └──────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    K3s Cluster (Production)                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           Self-Hosted Runner (on K3s node)               │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌────────────────┐   │    │
│  │  │ Pull Images │  │Apply K8s    │  │ Update         │   │    │
│  │  │ from Docker │  │Manifests    │  │ Deployments    │   │    │
│  │  │ Hub         │  │             │  │                │   │    │
│  │  └─────────────┘  └─────────────┘  └────────────────┘   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│         ┌────────────────────┼────────────────────┐              │
│         ▼                    ▼                    ▼              │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐        │
│  │ PostgreSQL  │     │  DBT Jobs   │     │ ML Pipeline │        │
│  │ ClickHouse  │     │  CronJobs   │     │  CronJobs   │        │
│  │    Redis    │     │             │     │             │        │
│  └─────────────┘     └─────────────┘     └─────────────┘        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Yêu cầu hệ thống

| Resource | Tối thiểu | Khuyến nghị |
|----------|-----------|-------------|
| OS | Ubuntu 20.04/22.04 LTS | Ubuntu 22.04 LTS |
| RAM | 8GB | 16GB+ |
| CPU | 4 cores | 8 cores+ |
| Disk | 50GB SSD | 100GB+ SSD |
| Network | Public IP | Static IP + Domain |

#### Các bước triển khai

**Bước 1: Cài đặt K3s trên server**

```bash
# Trên server Ubuntu
curl -sfL https://get.k3s.io | sh -

# Kiểm tra cài đặt
sudo kubectl get nodes
```

**Bước 2: Cấu hình GitHub Secrets**

Vào **GitHub Repository → Settings → Secrets and variables → Actions**, thêm:

| Secret | Mô tả | Ví dụ |
|--------|-------|-------|
| `DOCKERHUB_USERNAME` | Username Docker Hub | `annduke128` |
| `DOCKERHUB_TOKEN` | Access Token Docker Hub | `dckr_pat_xxx` |
| `POSTGRES_PASSWORD` | Mật khẩu PostgreSQL | `secure_password` |
| `CLICKHOUSE_PASSWORD` | Mật khẩu ClickHouse | `secure_password` |

**Bước 3: Setup Self-Hosted Runner**

```bash
# Trên K3s server, chạy với quyền root
cd /root

# Download runner (thay YOUR_TOKEN bằng token từ GitHub)
mkdir actions-runner && cd actions-runner
curl -o actions-runner-linux-x64-2.311.0.tar.gz \
  -L https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz
tar xzf actions-runner-linux-x64-2.311.0.tar.gz

# Cấu hình và chạy
./config.sh --url https://github.com/YOUR_USERNAME/YOUR_REPO --token YOUR_TOKEN
./run.sh
```

**Bước 4: Triển khai lần đầu**

```bash
# Từ repository local, push code lên main
git add .
git commit -m "Initial K3s deployment"
git push origin main
```

GitHub Actions sẽ tự động:
1. Build 3 Docker images: `hasu-ml-pipeline`, `hasu-dbt`, `hasu-sync-tool`
2. Push lên Docker Hub
3. Deploy lên K3s qua self-hosted runner

**Bước 5: Chạy pipeline trên K3s**

```bash
# Từ local machine (có kubectl kết nối đến K3s)
make app-k3s DOCKERHUB_USERNAME=yourusername

# Hoặc chạy từng bước riêng lẻ
make k3s-sync        # Chỉ chạy sync
make k3s-dbt         # Chỉ chạy DBT
make k3s-ml-train    # Chỉ train model
make k3s-ml-predict  # Chỉ predict
```

#### Commands thường dùng (K3s)

```bash
# Kiểm tra status
make k8s-status          # Xem tất cả resources
kubectl get pods -n hasu-ml
kubectl get jobs -n hasu-ml

# Xem logs
kubectl logs -n hasu-ml job/sync-data
kubectl logs -n hasu-ml job/dbt-build
kubectl logs -n hasu-ml job/ml-train

# Port forward để truy cập local
kubectl port-forward svc/airflow 8080:8080 -n hasu-ml
kubectl port-forward svc/superset 8088:8088 -n hasu-ml
```

📖 **Xem chi tiết**: [k8s/README.md](k8s/README.md)

---

## 📊 So sánh 2 cách triển khai

| Tiêu chí | Docker Compose | K3s + GitHub Actions |
|----------|---------------|---------------------|
| **Mục đích** | Dev/Test | Production |
| **Độ phức tạp** | Thấp | Cao |
| **CI/CD** | Manual | Tự động (GitHub Actions) |
| **Scaling** | Vertical only | Horizontal + Vertical |
| **High Availability** | Không | Có (multi-node) |
| **Auto-restart** | Docker restart | Kubernetes self-healing |
| **Resource Management** | Basic | Advanced (limits, quotas) |
| **Monitoring** | Basic logs | Full K8s observability |
| **SSL/TLS** | Manual | Cert-manager tự động |
| **Backup** | Manual | Velero/PVC backup |

### Khi nào dùng cái nào?

**Dùng Docker Compose khi:**
- 🔧 Đang phát triển tính năng mới
- 🧪 Cần test nhanh trên local
- 💻 Máy tính cá nhân, không có server riêng
- 🎓 Học tập, demo, proof-of-concept

**Dùng K3s khi:**
- 🚀 Deploy production thực tế
- 👥 Có nhiều user truy cập
- 📈 Cần auto-scaling theo load
- 🔄 Yêu cầu CI/CD tự động
- 💼 Doanh nghiệp, có đội ngũ vận hành

---

## 🔍 Kiểm tra Healthcheck

### Docker Compose

```bash
cd docker
make health
make logs
```

### K3s

```bash
# Check all pods
kubectl get pods -n hasu-ml

# Check logs
kubectl logs -f deployment/postgres -n hasu-ml
kubectl logs -f deployment/clickhouse -n hasu-ml

# Check events
kubectl get events -n hasu-ml --sort-by='.lastTimestamp'
```

---

## 📁 Import dữ liệu CSV

### Tự động (Airflow Schedule)

Hệ thống tự động chạy pipeline thông qua **Apache Airflow** với 2 DAGs:

| DAG | Lịch chạy | Mô tả |
|-----|-----------|-------|
| **csv_daily_import** | 2h sáng hàng ngày | Import CSV/Excel → PostgreSQL |
| **retail_weekly_ml** | 4h sáng Chủ nhật | Sync CH → DBT → Train ML → Forecast |

**Luồng pipeline:**
```
Hàng ngày 2am:    CSV/Excel ──► PostgreSQL (csv_daily_import)
                         │
Hàng tuần CN 4am:       ▼
              PostgreSQL ──► ClickHouse (sync)
                    │
                   DBT transforms
                    │
               Train ML models
                    │
               Generate forecasts
```

**Truy cập Airflow Web UI:**
- K3s: http://192.168.102.17:30080
- Docker: http://localhost:8085
- Username/Password: admin/admin

> **⚠️ Lưu ý**: Các DAG mặc định ở trạng thái **Paused**. Vào Airflow UI → DAGs → Bật (Unpause) để kích hoạt lịch tự động.

### Import thủ công (⚡ Python ETL - Khuyến nghị)

ETL Pipeline xử lý dữ liệu CSV/Excel → PostgreSQL (OLTP) → ClickHouse (OLAP):

**K3s (Production):**
```bash
# Chạy ETL độc lập
make k3s-spark-etl      # Chỉ chạy ETL
make k3s-spark          # Interactive mode (hỏi trước khi chạy)

# Hoặc chạy full pipeline
make app-k3s            # Full pipeline: ETL → DBT → ML
```

**Docker (Development):**
```bash
cd docker

# Chạy ETL (sử dụng Python + PySpark)
make etl-python         # ETL với Python
make sync-to-ch         # Legacy sync (nếu cần)

# Hoặc chạy full pipeline
make app
```

### ⚡ Kiến trúc ETL

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   CSV/Excel     │────▶│   Python ETL     │────▶│   PostgreSQL    │
│   Input Files   │     │   (PySpark)      │     │   (OLTP)        │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                                                          ▼
                                                  ┌─────────────────┐
                                                  │   ClickHouse    │
                                                  │   (OLAP/DW)     │
                                                  └─────────────────┘
```

**Luồng xử lý:**
1. **Products**: Đọc `DanhSachSanPham*.csv` → Parse nhóm hàng 3 cấp → PostgreSQL `products`
2. **Sales**: Đọc `BaoCaoBanHang*.xlsx` → Trích xuất giao dịch → PostgreSQL `transactions` + `transaction_details`
3. **Sync**: Đồng bộ từ PostgreSQL → ClickHouse `stg_products`, `stg_transactions`, `stg_transaction_details`

| Metric | Performance |
|--------|-------------|
| Products | ~16,000 records |
| Transactions | ~7,500 records |
| Transaction Details | ~16,000 records |
| Total Time | ~5-10 giây |

### Import thủ công (Legacy - Deprecated)

> ⚠️ **Deprecated:** Sử dụng Pandas, chậm hơn Spark 5-10x

```bash
# Docker (Legacy)
cd docker
make sync-to-ch

# K3s (Legacy)
make k3s-sync-legacy
```

---

## 🔧 Chạy DBT Project

### Cấu trúc DBT

```
dbt_retail/
├── models/
│   ├── staging/          # Làm sạch dữ liệu gốc
│   ├── intermediate/     # Transform trung gian
│   └── marts/            # Facts & Dimensions
├── seeds/                # Dữ liệu tham chiếu
└── macros/               # Hàm tiện ích
```

### Commands

**Docker:**
```bash
cd docker
make dbt-deps           # Install dependencies
make dbt-seed           # Load seeds
make dbt-build          # Build all models
make dbt-test           # Run tests
```

**K3s:**
```bash
make k3s-dbt
# Hoặc
kubectl apply -f k8s/05-ml-pipeline/job-dbt-build.yaml -n hasu-ml
```

**Native (không cần Docker):**
```bash
cd dbt_retail
dbt deps
dbt seed
dbt build --select staging,marts
```

---

## 🤖 Chạy ML Models

### Yêu cầu dữ liệu cho Training

| Mức độ | Ngày dữ liệu | Lag features | Độ tin cậy |
|--------|--------------|--------------|------------|
| **Minimum** | 2+ ngày | lag_1 | ⚠️ LOW |
| **Recommended** | 31+ ngày | lag_1, lag_7, lag_14, lag_30 | ✅ HIGH |
| **Optimal** | 90+ ngày | Đầy đủ + rolling ổn định | 🌟 HIGH |

> **Lưu ý:** Nếu dữ liệu < 31 ngày, lag_30 sẽ không được tạo. Nếu < 2 ngày, training sẽ fail.

### Training với Optuna Tuning

**Docker:**
```bash
cd docker
make ml                 # Train (50 trials)
make ml-fast            # Train nhanh (no tuning)
make ml-optimal         # Train tối ưu (100 trials)
make ml-all             # Train + Predict + Email
```

**K3s:**
```bash
make k3s-ml-train       # Train models
make k3s-ml-predict     # Generate predictions
```

### Chi tiết Hyperparameter Tuning

| Parameter | Range | Ý nghĩa |
|-----------|-------|---------|
| `max_depth` | 3-10 | Độ sâu cây |
| `learning_rate` | 0.01-0.3 | Tốc độ học |
| `subsample` | 0.6-1.0 | Sampling ratio |
| `colsample_bytree` | 0.6-1.0 | Feature sampling |

### Data Validation trong Training

Training pipeline tự động kiểm tra:

```
✅ Loaded 150,420 rows
   📊 Unique days in data: 75
   📊 Available lag features: [1, 7, 14, 30]
   ✅ Time-series continuity: Good (75/75 days)

🔧 Creating features...
✅ Created 25 features
   📊 Lag features created: ['lag_1_quantity', 'lag_7_quantity', 'lag_14_quantity', 'lag_30_quantity']
      - lag_1_quantity: 142,380 non-zero values (94.6%)
      - lag_7_quantity: 138,950 non-zero values (92.3%)
      - lag_14_quantity: 132,500 non-zero values (88.0%)
      - lag_30_quantity: 115,200 non-zero values (76.5%)
```

### Cold Start Handling

Sản phẩm có < 2 ngày dữ liệu sẽ được xử lý bằng **category median fallback**:

```python
predicted_qty = category_median * seasonal_factor / 7
```

Xem chi tiết: [ml_pipeline/ML_EXPLAIN.md](ml_pipeline/ML_EXPLAIN.md)

---

## 🔄 Airflow Workflow Orchestration

Hệ thống sử dụng **Apache Airflow 2.8** để tự động hóa data pipeline với 2 DAGs chính:

### 📅 Lịch trình DAGs

| DAG | Tần suất | Mô tả | Lệnh trigger |
|-----|----------|-------|--------------|
| **csv_daily_import** | 2h sáng hàng ngày | Import CSV/Excel → PostgreSQL | `make airflow-trigger csv_daily_import` |
| **retail_weekly_ml** | 4h sáng Chủ nhật | Full ML Pipeline (Sync→DBT→Train→Predict) | `make airflow-trigger retail_weekly_ml` |

### 🔄 Chi tiết retail_weekly_ml Pipeline

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│ 1. sync_pg_to_ch    │───▶│ 2. dbt_run_models   │───▶│ 3. dbt_run_tests    │
│    PostgreSQL→CH    │    │    Transform data   │    │    Data quality     │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
          │                                                 │
          ▼                                                 ▼
┌─────────────────────┐    ┌─────────────────────┐
│ 5. refresh_superset │◄───│ 4. train_models     │
│    Cache refresh    │    │    XGBoost + Optuna │
└─────────────────────┘    └─────────────────────┘
                                    │
                                    ▼
                           ┌─────────────────────┐
                           │ 6. generate_forecast│
                           │    Dự báo tuần tới  │
                           └─────────────────────┘
```

### 🔧 Truy cập Airflow UI

| Môi trường | URL | Credentials |
|------------|-----|-------------|
| Docker | http://localhost:8085 | admin/admin |
| K3s | http://192.168.102.17:30080 | admin/admin |

> **⚠️ Lưu ý**: Các DAG mặc định ở trạng thái **Paused**. Vào Airflow Web UI → DAGs → Unpause để kích hoạt lịch tự động.

### 🚀 Commands

```bash
# Trigger DAG thủ công
make airflow-trigger retail_weekly_ml
make airflow-trigger csv_daily_import

# Xem logs
kubectl logs -n hasu-ml deployment/airflow-web -f
kubectl logs -n hasu-ml deployment/airflow-scheduler -f

# Port-forward để truy cập UI (nếu dùng K3s)
kubectl port-forward -n hasu-ml svc/airflow-web 8085:8080
```

---

## 📊 Kết nối Superset BI

### Truy cập UI

| Môi trường | URL | Credentials |
|------------|-----|-------------|
| Docker | http://localhost:8088 | admin / admin |
| K3s | http://node-ip:30088 | admin / admin |

### Database Connections

**PostgreSQL:**
```
postgresql://retail_user:retail_password@postgres:5432/retail_db
```

**ClickHouse:**
```
clickhouse+http://default:clickhouse_password@clickhouse:8123/retail_dw
```

---

## 🛠️ Troubleshooting

### Docker Compose

```bash
# Port đã được sử dụng
sudo lsof -i :5432

# Container unhealthy
cd docker
make restart
make logs

# Disk full
make clean
make disk
```

### K3s

```bash
# Pod không start
kubectl logs -f deployment/postgres -n hasu-ml
kubectl get events -n hasu-ml --sort-by='.lastTimestamp'

# PVC pending
kubectl get pvc -n hasu-ml
kubectl describe pvc <pvc-name> -n hasu-ml

# Image pull failed
kubectl get secret dockerhub-credentials -n hasu-ml
# Re-apply secrets từ GitHub Actions hoặc manually
```

---

## 📞 Commands Reference

### Root Makefile Commands

```bash
# Development (Docker)
make app                # Run full pipeline locally

# Production (K3s) - Python ETL
make app-k3s            # Run full pipeline on K3s
make k3s-spark-etl      # ⚡ Python ETL only (CSV → PostgreSQL → ClickHouse)
make k3s-spark          # Interactive ETL (hỏi trước khi chạy)
make k3s-dbt            # DBT build only
make k3s-ml-train       # ML training only
make k3s-ml-predict     # ML prediction only

# Production (K3s) - Legacy (Deprecated)
make k3s-sync           # ⚠️ Legacy sync - use k3s-spark-etl instead

# K8s Management
make k8s-deploy         # Deploy/Update K3s resources
make k8s-deploy-all     # Full deployment
make k8s-status         # Check status
make k8s-logs           # View logs
make k8s-delete         # Delete all resources
```

### Python ETL Commands

```bash
# K3s
make k3s-spark-etl      # Run Python ETL Job
make k3s-spark          # Interactive ETL mode
kubectl logs -n hasu-ml job/spark-etl  # Xem logs

# Docker (Legacy Spark - Deprecated)
cd docker
make spark-up           # Start Spark cluster (nếu cần)
make spark-etl          # Run Spark ETL (legacy)
make spark-down         # Stop Spark cluster
```

---

## 📊 ML Pipeline Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                     ML PIPELINE FLOW                            │
└─────────────────────────────────────────────────────────────────┘

Data Loading          Validation           Feature Engineering
     │                      │                         │
     ▼                      ▼                         ▼
┌─────────┐          ┌─────────────┐          ┌─────────────────┐
│ fct_    │          │ • quantity>0│          │ • Time features │
│regular_ │    →     │ • revenue>0 │    →     │ • Lag features  │
│  sales  │          │ • >=2 days  │          │ • Rolling stats │
└─────────┘          │ • continuity│          │ • Seasonal      │
                     └─────────────┘          └─────────────────┘
                                                          │
                       Training                           │
                          │                               │
     ┌────────────────────┼────────────────────┐         │
     ▼                    ▼                    ▼         │
┌──────────┐      ┌──────────────┐      ┌──────────┐     │
│ Model 1  │      │   Model 2    │      │  Optuna  │◄────┘
│ Product  │      │  Category    │      │  Tuning  │
│  MdAPE   │      │   MAPE       │      │Log+ MSE  │
└──────────┘      └──────────────┘      └──────────┘
     │                    │
     └────────────────────┘
            │
            ▼
┌──────────────────────────┐
│  Multi-View Evaluation   │
│  • MAE  (units)          │
│  • MdAPE (%)  (Model 1)  │
│  • MAPE (%)   (Model 2)  │
│  • RMSE (units)          │
└──────────────────────────┘
     │                    │
     └────────────────────┘
                │
                ▼
     ┌────────────────────┐
     │    Prediction      │
     │  • Top 50 ABC      │
     │  • 7-day forecast  │
     │  • Cold start      │
     │    handling        │
     └────────────────────┘
                │
                ▼
     ┌────────────────────┐
     │      Output        │
     │  • ClickHouse      │
     │  • PostgreSQL      │
     │  • CSV Export      │
     │  • Email Report    │
     └────────────────────┘
```

### Data Quality Gates

| Stage | Check | Threshold | Fail Action |
|-------|-------|-----------|-------------|
| Load | Records loaded | > 0 | Stop |
| Validate | Unique days | >= 2 | Stop |
| Validate | Continuity | >= 80% | Warning |
| Feature | Lag features | >= 1 | Stop |
| Train | Valid targets | > 0 | Stop |
| Predict | Forecast count | > 0 | Alert |

### Chiến lược đánh giá Đa góc nhìn (Multi-View Evaluation)

Hệ thống ML sử dụng **3 metrics chính** để đánh giá toàn diện chất lượng dự báo:

```
┌─────────────────────────────────────────────────────────────┐
│                    ĐA GÓC NHÌN METRICS                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📏 MAE (Mean Absolute Error)                               │
│     → Trung bình mỗi ngày kho bị dư/thiếu bao nhiêu đơn vị │
│     → Đơn vị: sản phẩm                                      │
│                                                             │
│  📈 MdAPE (Median Absolute Percentage Error)               │
│     → 50% ngày có sai số dưới ngưỡng này                   │
│     → Phát hiện ngày bị sai số đột biến                     │
│     → Model 1 (Product): Primary metric                    │
│                                                             │
│  📊 MAPE (Mean Absolute Percentage Error)                  │
│     → Sai số % trung bình                                  │
│     → Model 2 (Category): Primary metric                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Chiến lược training:**
- **Unified**: Chỉ dùng Optuna tuning (đã xóa train_model không tuning)
- **Model 1 (Product)**: Tối ưu MdAPE - robust với outliers
- **Model 2 (Category)**: Tối ưu MAPE - đánh giá tổng thể
- **Đánh giá**: Log đầy đủ MAE, MdAPE, MAPE để có cái nhìn đa chiều

**Ví dụ output:**
```python
📊 Validation Metrics:
   📏 MAE:   12.35      ← Trung bình mỗi ngày kho bị dư/thiếu (đơn vị)
   📈 MAPE:  15.73%     ← Sai số % trung bình
   📉 MdAPE: 6.21%      ← 50% ngày sai số dưới ngưỡng này
   📐 RMSE:  18.90
```

---

## 🏪 Hệ thống Phân loại Cửa hàng

### 5 Loại cửa hàng

| Mã | Peer Group | Tên tiếng Việt | Đặc điểm |
|----|------------|----------------|----------|
| **KPDT** | UP | Khu phố đô thị | Khu dân cư đô thị, lưu lượng khách ổn định |
| **KCC** | AP | Khu chung cư | Tập trung cư dân, nhu cầu thiết yếu cao |
| **KCN** | IZ | Khu công nghiệp | Gần nhà máy, giờ cao điểm theo ca |
| **CTT** | TM | Chợ truyền thống | Chợ đầu mối, khách hàng đa dạng |
| **KVNT** | RL | Khu vực nông thôn | Vùng sâu vùng xa, nhu cầu cơ bản |

---

## 📊 Phân loại ABC

| Class | Phân vị doanh thu | Đặc điểm |
|-------|-------------------|----------|
| **A** | Top 80% | Sản phẩm chủ lực, ~20% SKU |
| **B** | 80% - 95% | Sản phẩm trung bình, ~30% SKU |
| **C** | Còn lại | Sản phẩm ít quan trọng, ~50% SKU |

---

## 📧 Email Notification System

Tự động gửi email cho các sự kiện:
- ML Training Success/Failure với data quality metrics
- ML Prediction Success/Failure với forecast summary
- Data quality alerts (cold start, missing data, zero predictions)

**Nội dung email training report:**
- Model performance metrics (MAE, MdAPE, MAPE)
- Data quality indicators (cold start %, missing dates, zero predictions)
- Feature importance top 5
- Comparison giữa Model 1 và Model 2
- Alerts với màu sắc (🔴 Error, 🟠 Warning, 🔵 Info)

**Nội dung email forecast report:**
- Tổng số sản phẩm được dự báo
- So sánh với tuần trước (last_week_sales)
- Top sản phẩm tăng/giảm mạnh nhất
- ABC classification distribution

**Docker:** Cấu hình trong `docker/.env`
**K3s:** Cấu hình trong GitHub Secrets (auto-inject vào K8s secrets)

---

## 📚 Tài liệu tham khảo

| File | Mô tả |
|------|-------|
| [AGENTS.md](AGENTS.md) | Hướng dẫn cho AI coding agents |
| [docker/README.md](docker/README.md) | Chi tiết Docker Compose |
| [k8s/README.md](k8s/README.md) | Chi tiết K3s deployment |
| [docs/SPARK_HYBRID_GUIDE.md](docs/SPARK_HYBRID_GUIDE.md) | Hướng dẫn Spark Hybrid ETL |
| [docs/MIGRATION_ETL_TO_SPARK.md](docs/MIGRATION_ETL_TO_SPARK.md) | Migration từ ETL cũ sang Spark |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Kiến trúc hệ thống chi tiết |

---

## 📄 License

MIT License

**Last Updated:** 2026-03-18

---

## 🆕 Cập nhật mới nhất (2026-03-16)

### ✅ Tính năng mới

| Tính năng | Mô tả | Status |
|-----------|-------|--------|
| **Purchase Order Generation** | Tự động tạo đơn đặt hàng dựa trên dự báo ML + tồn kho + quy đổi | ✅ Hoàn thành |
| **Inventory Integration** | Import tồn kho trực tiếp vào ClickHouse | ✅ Hoàn thành |
| **Quy đổi ĐVT** | Hỗ trợ tỉ lệ quy đổi từ Excel (cột Quy đổi) | ✅ Hoàn thành |
| **Price Fix** | Fix giá sản phẩm = 0 trong transaction_details | ✅ Hoàn thành |

### 📦 Purchase Order Generation ⭐ Cập nhật Safety Stock

Tạo đơn đặt hàng tự động với **Tồn kho an toàn (Safety Stock)**:

**Công thức Safety Stock:**
```
Safety Stock = (Nhu cầu cao nhất × Lead time max) - (Nhu cầu TB × Lead time TB)
```

**Công thức Lượng cần nhập (cập nhật):**
```
Lượng cần nhập = MAX(Dự báo 7 ngày, Tồn kho tối ưu + Safety Stock) - Tồn kho hiện tại
Đơn đặt hàng = ROUND_UP(Cần nhập / Quy đổi) × Quy đổi
```

**Tham số:**
| Tham số | Mặc định | Mô tả |
|---------|----------|-------|
| `lead_time_max` | 7 ngày | Lead time tối đa |
| `lead_time_avg` | 5 ngày | Lead time trung bình |

**Cách sử dụng:**
```bash
# Với lead time mặc định
python ml_pipeline/xgboost_forecast.py --mode po --top-n 50

# Hoặc trong Python
forecaster.generate_purchase_order_csv(lead_time_max=10, lead_time_avg=6)
```

### 📊 Inventory Import trực tiếp ClickHouse

File `BaoCaoXuatNhapTon_*.xlsx` được import **trực tiếp** vào ClickHouse (không qua PostgreSQL):

```python
# Trong etl_main.py
def process_inventory_pyspark(spark):
    # Đọc từ Excel
    # Ghi trực tiếp vào ClickHouse.staging_inventory_transactions
```

### 🔧 Docker Images

| Image | Tag | Thay đổi |
|-------|-----|----------|
| annduke/hasu-spark-etl | real-final-v18 | Thêm inventory import, quy_doi column |
| annduke/hasu-ml-pipeline | latest | Thêm purchase order generation |

---

## 🆕 Cập nhật (2026-03-18)

### 🔄 Airflow Documentation

Thêm tài liệu chi tiết về Airflow Workflow Orchestration:

| Nội dung | Vị trí |
|----------|--------|
| **Airflow section** | README.md - sau ML Models |
| **DAG details** | AGENTS.md - phần Airflow DAGs |
| **Workflow diagram** | Chi tiết 6 bước retail_weekly_ml |
| **Commands** | Trigger DAG, view logs, port-forward |

> **⚠️ Lưu ý quan trọng**: DAGs mặc định ở trạng thái **Paused**. Cần unpause trong Airflow UI để kích hoạt lịch tự động.

### 🤖 ML Pipeline Refactoring ⭐

**Đơn giản hóa ML pipeline** - Loại bỏ complexity, tập trung vào chính xác.

**Thay đổi chính:**

| | Trước | Sau |
|---|---|---|
| **Training functions** | `train_model()` + `train_model_optuna()` | Chỉ `train_model_optuna()` |
| **Tuning** | Optional (`use_tuning=True/False`) | Luôn tuning |
| **Model 1 (Product)** | MdAPE primary | **MdAPE** primary (robust với outliers) |
| **Model 2 (Category)** | MAPE primary | **MAPE** primary (đánh giá tổng thể) |

**Chiến lược tối ưu:**

| Model | Primary Metric | Mục đích |
|-------|---------------|----------|
| **Model 1 (Product)** | MdAPE | Robust với outliers của từng sản phẩm |
| **Model 2 (Category)** | MAPE | Đánh giá tổng thể category trend |

**Code changes:**
- `xgboost_forecast.py`: Xóa `train_model()` không tuning, chỉ giữ `train_model_optuna()`
- `train_all_models()`: Bỏ parameter `use_tuning`, luôn dùng Optuna
- Cập nhật callers: `train_models.py`, `xgboost_forecast.py` main block

**Last Updated:** 2026-03-18

