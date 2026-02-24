# Docker Deployment Package

Thư mục này chứa tất cả các file Docker và cấu hình để deploy Retail Data Pipeline.

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

## 🚀 Triển khai

Sử dụng Makefile (khuyến nghị):

```bash
# Copy environment file
cp .env.example .env
# (Sửa các giá trị trong .env nếu cần)

# Xem tất cả commands
make help

# Chạy infrastructure cơ bản (Redis, PostgreSQL, ClickHouse, Airflow, Superset)
make up

# Chạy với ML Pipeline
make up-ml

# Chạy với Sync Tool
make up-sync

# Chạy tất cả services
make up-all
```

Hoặc dùng docker-compose trực tiếp:

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
```

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

## ⚙️ Profiles

- **default**: Các service cơ bản (redis, postgres, clickhouse, airflow, superset)
- **ml**: ML Pipeline service
- **sync**: Sync Tool service
- **init**: Init scripts (superset-clickhouse-init)
- **donotstart**: DBT (chỉ chạy khi gọi explicitly)

## 🔧 Lệnh thường dùng

### Makefile Commands (khuyến nghị)

```bash
# Xem logs
make logs                    # Tất cả services
make logs-ml-pipeline        # Service cụ thể

# Restart service
make restart

# Build lại image
make build
make build-service SERVICE=ml-pipeline

# Dọn dẹp
make down-v      # Stop và xóa volumes
make clean       # Dọn Docker cache
make disk        # Xem disk usage

# Data Pipeline
make sync-to-ch           # Sync PG → CH
make dbt-build            # Build all models
make dbt-build-staging    # Build staging only
make dbt-build-marts      # Build marts only
make pipeline-full        # Full pipeline

# ML Pipeline
make ml                   # Train với Optuna
make ml-fast              # Train nhanh (no tuning)
make ml-optimal           # Train tối ưu (100 trials)
make ml-all               # Train + Predict + Email
make ml-predict           # Predict only

# Database CLI
make psql                 # PostgreSQL CLI
make clickhouse           # ClickHouse CLI
make redis                # Redis CLI

# Health Check
make health               # Check all
make health-postgres      # Check PostgreSQL
make health-clickhouse    # Check ClickHouse
make health-redis         # Check Redis
```

### Docker Compose trực tiếp

```bash
# Xem logs
docker-compose logs -f [service-name]

# Restart service
docker-compose restart [service-name]

# Scale service (chỉ cho stateless services)
docker-compose up -d --scale ml-pipeline=3

# Build lại image
docker-compose build --no-cache [service-name]

# Dọn dẹp
docker-compose down -v  # Xóa cả volumes
docker system prune -a   # Dọn images không dùng
```

## 📝 Environment Variables

Xem file `.env.example` để biết các biến môi trường có thể cấu hình.
