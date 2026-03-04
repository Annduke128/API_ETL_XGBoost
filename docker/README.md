# Docker Deployment Package

Thư mục này chứa tất cả các file Docker và cấu hình để chạy Retail Data Pipeline trong môi trường **Development/Testing**.

> 🎯 **Mục đích**: Chạy local, phát triển tính năng, test nhanh
> 
> 🚀 **Production**: Xem [k8s/README.md](../k8s/README.md) để triển khai trên K3s

---

## 📋 Yêu cầu hệ thống

| Resource | Tối thiểu | Khuyến nghị |
|----------|-----------|-------------|
| RAM | 8GB | 16GB+ |
| Disk | 20GB free | 50GB+ SSD |
| Docker | 24.0+ | Latest |
| Docker Compose | 2.20+ | Latest |

---

## 📁 Cấu trúc thư mục

```
docker/
├── docker-compose.yml          # File chính định nghĩa tất cả services
├── .env.example                # Mẫu biến môi trường
├── Makefile                    # Commands cho Docker operations
├── README.md                   # Hướng dẫn này
│
├── data_cleaning/              # Sync Tool - PostgreSQL to ClickHouse
│   ├── Dockerfile
│   └── requirements.txt
│
├── dbt_retail/                 # DBT Data Transformation
│   └── Dockerfile
│
├── ml_pipeline/                # ML Pipeline Service
│   ├── Dockerfile
│   ├── Dockerfile.gpu          # Phiên bản có GPU support
│   └── requirements.txt
│
├── superset/                   # Apache Superset BI
│   ├── docker-bootstrap.sh
│   ├── superset_config.py
│   └── create_clickhouse_conn.py
│
└── init/                       # Khởi tạo database
    ├── postgres/
    └── clickhouse/
```

---

## 🚀 Quick Start

```bash
# 1. Vào thư mục docker
cd docker

# 2. Copy environment file
cp .env.example .env
# (Sửa các giá trị trong .env nếu cần)

# 3. Khởi động
make up                 # Infrastructure cơ bản
# hoặc
make up-ml              # Kèm ML Pipeline
# hoặc  
make up-all             # Tất cả services

# 4. Kiểm tra
make status
make health
```

---

## 📋 Danh sách Services

| Service | Port | Mô tả | Profile |
|---------|------|-------|---------|
| redis | 6379 | Cache & Buffer | default |
| postgres | 5432 | OLTP Database | default |
| clickhouse | 8123, 9000 | Data Warehouse | default |
| dbt | - | Data Transformation | donotstart |
| airflow-webserver | 8085 | Workflow Scheduler | default |
| superset-web | 8088 | BI Dashboard | default |
| ml-pipeline | - | ML Training & Prediction | ml |
| sync-tool | - | Batch ETL Sync | sync |

### Profiles

- **default**: Các service cơ bản (redis, postgres, clickhouse, airflow, superset)
- **ml**: ML Pipeline service
- **sync**: Sync Tool service
- **init**: Init scripts (superset-clickhouse-init)
- **donotstart**: DBT (chỉ chạy khi gọi explicitly)

---

## 🔧 Lệnh thường dùng

### Makefile Commands (khuyến nghị)

```bash
# Khởi động / Dừng
make up                 # Start infrastructure
make up-ml              # Start with ML Pipeline
make up-all             # Start all services
make down               # Stop services
make down-v             # Stop + remove volumes

# Xem logs
make logs               # Tất cả services
make logs-ml-pipeline   # Service cụ thể

# Restart / Build
make restart            # Restart all
make build              # Build images
make build-service SERVICE=ml-pipeline  # Build specific

# Dọn dẹp
make clean              # Dọn Docker cache
make disk               # Xem disk usage

# Data Pipeline
make sync-to-ch         # Sync PG → CH
make dbt-build          # Build all models
make dbt-build-staging  # Build staging only
make dbt-build-marts    # Build marts only
make pipeline-full      # Full pipeline

# ML Pipeline
make ml                 # Train với Optuna
make ml-fast            # Train nhanh (no tuning)
make ml-optimal         # Train tối ưu (100 trials)
make ml-all             # Train + Predict + Email
make ml-predict         # Predict only

# Database CLI
make psql               # PostgreSQL CLI
make clickhouse         # ClickHouse CLI
make redis              # Redis CLI

# Health Check
make health             # Check all
make health-postgres    # Check PostgreSQL
make health-clickhouse  # Check ClickHouse
make health-redis       # Check Redis
```

### Docker Compose trực tiếp

```bash
# Chạy infrastructure cơ bản
docker-compose up -d redis postgres clickhouse

# Chạy thêm Airflow
docker-compose up -d airflow-postgres airflow-init airflow-webserver airflow-scheduler

# Chạy thêm Superset
docker-compose up -d superset-db superset-cache superset-init superset-web

# Chạy ML Pipeline (nếu cần)
docker-compose --profile ml up -d ml-pipeline

# Chạy Sync Tool (nếu cần)
docker-compose --profile sync up -d sync-tool

# Xem logs
docker-compose logs -f [service-name]

# Restart service
docker-compose restart [service-name]

# Scale service (chỉ cho stateless services)
docker-compose up -d --scale ml-pipeline=3

# Build lại image
docker-compose build --no-cache [service-name]

# Dọn dẹp
docker-compose down -v      # Xóa cả volumes
docker system prune -a      # Dọn images không dùng
```

---

## 📝 Environment Variables

Xem file `.env.example` để biết các biến môi trường có thể cấu hình.

### Các biến quan trọng

```bash
# Database
POSTGRES_USER=retail_user
POSTGRES_PASSWORD=retail_password
POSTGRES_DB=retail_db

CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=clickhouse_password
CLICKHOUSE_DB=retail_dw

# Airflow
AIRFLOW_USERNAME=admin
AIRFLOW_PASSWORD=admin

# Superset
SUPERSET_ADMIN_USER=admin
SUPERSET_ADMIN_PASSWORD=admin

# Email (cho ML notifications)
EMAIL_SENDER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
```

---

## 🔍 Troubleshooting

### Port đã được sử dụng

```bash
sudo lsof -i :5432
# Hoặc thay đổi port trong .env
```

### Container unhealthy

```bash
make restart
make logs
```

### Disk full

```bash
make clean
make disk
docker system prune -f
docker volume prune -f
```

### Permission denied

```bash
# Fix Docker permissions
sudo usermod -aG docker $USER
newgrp docker
```

---

## 🔄 So sánh với K3s Deployment

| Tiêu chí | Docker Compose | K3s |
|----------|---------------|-----|
| **Mục đích** | Dev/Test | Production |
| **Độ phức tạp** | Thấp | Cao |
| **Scaling** | Vertical | Horizontal + Vertical |
| **CI/CD** | Manual | GitHub Actions |
| **High Availability** | Không | Có |
| **Multi-node** | Không | Có |

👉 **Triển khai Production**: Xem [k8s/README.md](../k8s/README.md)

---

## 📚 Tài liệu liên quan

- [Root README.md](../README.md) - Tổng quan dự án
- [AGENTS.md](../AGENTS.md) - Hướng dẫn cho AI agents
- [k8s/README.md](../k8s/README.md) - Triển khai K3s
