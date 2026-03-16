# Changelog

Tất cả các thay đổi quan trọng của dự án sẽ được ghi lại ở đây.

## [Unreleased] - 2026-03-16

### 🔧 Fixed

#### ClickHouse Connection
- **Đổi port từ HTTP (8123) sang Native (9000)** cho tất cả components
  - ML Pipeline: Sửa `db_connectors.py` dùng `clickhouse-driver` thay vì HTTP API
  - DBT: Cập nhật `profiles.yml` driver từ `http` sang `native`
  - Spark ETL: Cập nhật JDBC URL thêm `?protocol=native`

#### ML Pipeline - Forecast Email
- **Fix query tuần trước**: Dùng `max_date` thay vì `today()` để lấy tuần gần nhất có dữ liệu
- **Fix numpy type casting**: Ép kiểu `str()` và `float()` cho các giá trị trong email
- **Thêm cột "Bán tuần qua"**: Hiển thị last_week_sales trong bảng forecast
- **Sửa cột xu hướng**: Hiển thị "Tăng/Giảm/Ổn định" với icon thay vì phần trăm

#### Inventory Calculation
- **Thống nhất công thức tồn kho**: 
  ```
  Tồn kho tối ưu = MAX(Dự báo 7 ngày, Tồn nhỏ nhất)
  Cần nhập = MAX(Tồn kho tối ưu - Tồn hiện tại, 0)
  ```
- **Sắp xếp theo cần nhập**: Bảng forecast sắp xếp theo "Đề xuất đặt tuần tới" giảm dần

#### DBT Models
- **Fix source name**: `raw_transactions` → `staging_transactions`
- **Fix date parsing**: Thêm `toDate(ngay)` cho cột String trong `stg_transactions_enriched.sql`

#### Airflow
- **Tạo user và database**: `CREATE USER airflow` và `CREATE DATABASE airflow`
- **Init Airflow DB**: Chạy `airflow db init` để tạo metadata tables

### 📦 Updated Docker Images
- `annduke/hasu-ml-pipeline:latest`
- `annduke/hasu-dbt:latest`
- `annduke/hasu-spark-etl:real-final-v19`

### 📝 Files Changed
- `ml_pipeline/db_connectors.py`
- `ml_pipeline/email_notifier.py`
- `ml_pipeline/xgboost_forecast.py`
- `dbt_retail/profiles.yml`
- `dbt_retail/Dockerfile`
- `dbt_retail/models/staging/stg_transactions_enriched.sql`
- `spark-etl/python_etl/etl_main.py`
- `k8s/02-config/configmap.yaml`
- `k8s/05-ml-pipeline/job-spark-etl.yaml`

---

## [2026-03-07] - Previous Release

### ✨ Added
- Initial ML Pipeline with XGBoost
- DBT models for retail analytics
- Airflow orchestration
- Docker Compose và K8s deployment
