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
9. [Kết nối Superset BI](#kết-nối-superset-bi)
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

Hệ thống tự động import CSV **hàng ngày lúc 2h sáng** thông qua Airflow DAG.

### Import thủ công (⚡ Spark Hybrid - Khuyến nghị)

**Docker:**
```bash
cd docker

# Khởi động Spark cluster (lần đầu)
make spark-up

# Chạy Spark ETL (CSV → PostgreSQL → ClickHouse)
make spark-etl

# Hoặc chạy full pipeline
make pipeline-spark
```

**K3s:**
```bash
# Deploy Spark cluster (lần đầu)
make spark-deploy

# Chạy Spark ETL
make k3s-spark

# Hoặc chạy full pipeline
make app-k3s  # Sử dụng Spark ETL by default
```

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

# Production (K3s) - Spark Hybrid ETL
make app-k3s            # Run full pipeline on K3s (uses Spark ETL)
make k3s-spark          # ⚡ Spark ETL only (CSV → PostgreSQL → ClickHouse)
make spark-deploy       # Deploy Spark cluster
make k3s-dbt            # DBT build only
make k3s-ml-train       # ML training only
make k3s-ml-predict     # ML prediction only

# Production (K3s) - Legacy (Deprecated)
make k3s-sync-legacy    # ⚠️ Legacy sync - use k3s-spark instead

# K8s Management
make k8s-deploy         # Deploy/Update K3s resources
make k8s-deploy-all     # Full deployment
make k8s-status         # Check status
make k8s-logs           # View logs
make k8s-delete         # Delete all resources
```

### Spark ETL Commands

```bash
# Docker
cd docker
make spark-up           # Start Spark cluster
make spark-etl          # Run Spark Hybrid ETL
make spark-status       # Check Spark status
make spark-down         # Stop Spark cluster

# K3s
make spark-deploy       # Deploy Spark to K3s
make spark-status       # Check Spark cluster
make spark-delete       # Remove Spark cluster
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
│  MdAPE   │      │   MAPE       │      │          │
└──────────┘      └──────────────┘      └──────────┘
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
- Model performance metrics (MdAPE, MAPE)
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

**Last Updated:** 2026-03-07
