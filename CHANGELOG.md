# Changelog

Tất cả các thay đổi quan trọng của dự án sẽ được ghi lại ở đây.

## [Unreleased] - 2026-03-25

### 🧹 Code Cleanup

#### Removed Files
- **`ml_pipeline/train_parallel.py`** - Orphan code, không được sử dụng ở bất cứ đâu
- **`ml_pipeline/xgboost_forecast_gpu_patch.py`** - Hacky patching approach

#### Added Native GPU Support
- GPU support được tích hợp **trực tiếp** vào `xgboost_forecast.py`
- Auto-detect GPU qua `nvidia-smi` khi `USE_GPU=true`
- Tự động chuyển `tree_method='gpu_hist'` (GPU) hoặc `'hist'` (CPU)

#### Updated Dockerfiles
- `Dockerfile.gpu` - Bỏ bước patch, copy files trực tiếp
- `Dockerfile` - Bỏ copy `xgboost_forecast_gpu_patch.py`

### ⚡ Spark ETL Enhancements

#### Auto-Move Processed Files
- File đã xử lý tự động chuyển sang `/csv_input/processed/`
- Tránh xử lý lại file cũ khi chạy ETL nhiều lần
- Tự động thêm timestamp nếu file đã tồn tại ở thư mục processed

#### Data Protection - Bảo vệ dữ liệu cũ
- **⚠️ BỎ DELETE+INSERT mode** - Chỉ dùng UPSERT để đảm bảo không mất dữ liệu
- `ON CONFLICT DO UPDATE` cho products (cập nhật nếu đã tồn tại)
- `ON CONFLICT DO NOTHING` cho transactions (bỏ qua nếu đã tồn tại)
- **KHÔNG BAO GIỜ TRUNCATE hoặc DELETE toàn bộ dữ liệu**

#### Logging cải tiến
- Log số records **trước** khi import
- Log số records **sau** khi import  
- Xác nhận rõ ràng: "DỮ LIỆU CŨ ĐƯỢC BẢO TOÀN"

#### CLI Arguments
```bash
# UPSERT mode (default - luôn giữ dữ liệu cũ)
python etl_main.py

# Custom directories
python etl_main.py --input-dir /data/csv --processed-dir /data/done
```

### 📝 Files Changed
- `ml_pipeline/xgboost_forecast.py` (+native GPU support)
- `ml_pipeline/Dockerfile`
- `ml_pipeline/Dockerfile.gpu`
- `ml_pipeline/train_parallel.py` (deleted)
- `ml_pipeline/xgboost_forecast_gpu_patch.py` (deleted)
- `spark-etl/python_etl/etl_main.py` (+auto-move, DELETE+INSERT mode, CLI args)
- `spark-etl/python_etl/etl_main_DELETE_INSERT.py` (deleted - merged into etl_main.py)

---

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
