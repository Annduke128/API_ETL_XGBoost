# Retail Data Pipeline - Hệ thống Data Warehouse cho ngành bán lẻ

Hệ thống data pipeline hoàn chỉnh với ETL tự động, Data Warehouse, BI Dashboard và ML Forecasting.

## 📋 Mục lục

1. [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
2. [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
3. [Triển khai](#triển-khai)
4. [Kiểm tra healthcheck](#kiểm-tra-healthcheck)
5. [Import dữ liệu CSV](#import-dữ-liệu-csv)
6. [Chạy DBT Project](#chạy-dbt-project)
7. [Chạy ML Models](#chạy-ml-models)
8. [Tùy chỉnh tham số](#tùy-chỉnh-tham-số)
9. [Kết nối Superset BI](#kết-nối-superset-bi)
10. [Troubleshooting](#troubleshooting)
11. [Hệ thống Phân loại Cửa hàng](#hệ-thống-phân-loại-cửa-hàng)
12. [Phân loại ABC & Quản lý Sản phẩm](#phân-loại-abc--quản-lý-sản-phẩm)
13. [Email Notification System](#email-notification-system)
14. [Assortment Analytics](#assortment-analytics)

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

## 🚀 Triển khai

Triển khai tất cả services trên một máy duy nhất sử dụng Docker Compose.

### Bước 1: Vào thư mục docker

```bash
cd retail_data_pipeline/docker
```

### Bước 2: Copy file môi trường

```bash
cp .env.example .env
# (Sửa các giá trị trong .env nếu cần)
```

### Bước 3: Khởi động hệ thống

```bash
# Khởi động infrastructure (khuyến nghị)
make up

# Hoặc khởi động với ML Pipeline
make up-ml

# Hoặc khởi động tất cả services
make up-all
```

**Services khởi động:**
- Redis (Cache)
- PostgreSQL (OLTP)
- ClickHouse (Data Warehouse)
- Airflow (Scheduler)
- Superset (BI Dashboard)

### Bước 4: Kiểm tra status

```bash
make status
make health
```

### Commands hữu ích

```bash
# Xem tất cả commands
make help

# Logs
make logs              # Tất cả services
make logs-ml-pipeline  # Service cụ thể

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

---

## 🔍 Kiểm tra Healthcheck

```bash
cd docker

# Kiểm tra tất cả services
make health

# Kiểm tra từng service
make health-postgres
make health-clickhouse
make health-redis

# Xem logs
make logs
make logs-ml-pipeline
```

---

## 📁 Import dữ liệu CSV

### Tự động (Airflow Schedule)

Hệ thống tự động import CSV **hàng ngày lúc 2h sáng** thông qua Airflow DAG.

### Import thủ công

```bash
cd docker
make sync-to-ch
```

### Copy file CSV

```bash
# Copy file vào thư mục
cp /path/to/your/file.csv csv_input/

# File sẽ được tự động xử lý
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

```bash
cd docker

make dbt-deps           # Install dependencies
make dbt-seed           # Load seeds
make dbt-build          # Build all models
make dbt-build-staging  # Build staging only
make dbt-build-marts    # Build marts only
make dbt-test           # Run tests
make dbt-docs           # Generate & serve docs
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

### Training với Optuna Tuning

```bash
cd docker

make ml                 # Train (50 trials)
make ml-fast            # Train nhanh (no tuning)
make ml-optimal         # Train tối ưu (100 trials)
make ml-all             # Train + Predict + Email
make ml-predict         # Generate predictions only
```

### Chi tiết Hyperparameter Tuning

| Parameter | Range | Ý nghĩa |
|-----------|-------|---------|
| `max_depth` | 3-10 | Độ sâu cây |
| `learning_rate` | 0.01-0.3 | Tốc độ học |
| `subsample` | 0.6-1.0 | Sampling ratio |
| `colsample_bytree` | 0.6-1.0 | Feature sampling |

---

## ⚙️ Tùy chỉnh tham số

### 1. Tham s trong dbt_project.yml

```yaml
vars:
  min_date: '2020-01-01'
  high_value_threshold: 1000000  # 1 triệu VND
  abc_a_threshold: 0.8
  abc_b_threshold: 0.95
```

### 2. Environment Variables

Sửa trong `docker/.env`:

```bash
POSTGRES_USER=retail_user
POSTGRES_PASSWORD=your_password
CLICKHOUSE_PASSWORD=your_password
EMAIL_SENDER=your-email@company.com
```

---

## 📊 Kết nối Superset BI

### Truy cập UI

- **URL:** http://localhost:8088
- **Username:** `admin`
- **Password:** `admin`

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

---

## 📞 Commands Reference

### Application Commands (Makefile gốc)

```bash
# Development
make install            # Install Python dependencies
make test               # Run tests
make format             # Format code
make lint               # Lint code

# DBT (native)
make dbt-deps           # Install DBT dependencies
make dbt-build          # Build models
make dbt-test           # Run tests

# ML (native)
make ml                 # Train ML
make ml-all             # Full ML pipeline
```

### Docker Commands (docker/Makefile)

```bash
cd docker

make up                 # Start infrastructure
make up-ml              # Start with ML
make up-all             # Start all
make down               # Stop services
make build              # Build images

make sync-to-ch         # Sync data
make dbt-build          # Build DBT
make ml-all             # Full ML pipeline
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
- ML Training Success/Failure
- ML Prediction Success/Failure

Cấu hình trong `docker/.env`:
```bash
EMAIL_SENDER=ml-pipeline@company.com
EMAIL_PASSWORD=your-app-password
```

---

## 📄 License

MIT License

**Last Updated:** 2026-02-24
# Test CI/CD
# Test CI/CD
