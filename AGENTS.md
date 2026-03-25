# AGENTS.md - ML Pipeline for Retail Sales Forecasting

> File hướng dẫn dành cho AI coding agents làm việc với dự án Retail ML Pipeline.
> Ngôn ngữ: **Tiếng Việt**

---

## 📋 Tổng quan dự án

**Retail ML Pipeline** là hệ thống machine learning pipeline hoàn chỉnh cho ngành bán lẻ:

- **ETL**: PySpark xử lý dữ liệu CSV quy mô lớn
- **Data Warehouse**: PostgreSQL (OLTP) + ClickHouse (OLAP)
- **BI Dashboard**: Apache Superset
- **ML Forecasting**: XGBoost + Optuna hyperparameter tuning với **native GPU support**
- **Orchestration**: Kubernetes CronJobs + Airflow
- **Email Notifications**: Gmail SMTP cho training và forecast reports

### 🆕 Cập nhật gần đây (2026-03-25)
- ✅ **Native GPU Support**: Tích hợp trực tiếp vào `xgboost_forecast.py`, tự động detect GPU qua `nvidia-smi`
- 🧹 **Code Cleanup**: Xóa `train_parallel.py` (orphan code) và `xgboost_forecast_gpu_patch.py` (hacky approach)
- 📁 **Spark ETL Auto-Move**: File đã xử lý tự động chuyển sang `/csv_input/processed/`
- 🛡️ **Data Protection**: Spark ETL chỉ dùng UPSERT, **KHÔNG BAO GIỜ** xóa dữ liệu cũ

---

## 🏗️ Cấu trúc thư mục

```
/home/hasu/
├── fixed_ml_pipeline/              # 🐍 ML Pipeline Source Code
│   ├── xgboost_forecast.py         # Main forecasting với GPU support
│   ├── train_models.py             # Training entry point
│   ├── email_notifier.py           # Email notifications
│   ├── db_connectors.py            # PostgreSQL & ClickHouse connectors
│   ├── pipeline_monitor.py         # Pipeline monitoring
│   ├── Dockerfile                  # CPU-only image
│   ├── Dockerfile.gpu              # GPU-enabled image
│   └── requirements.txt              # Python dependencies
│
├── actions-runner/_work/API_ETL_XGBoost/  # 🐳 Docker & K8s Configs
│   ├── spark-etl/                  # PySpark ETL
│   │   ├── python_etl/etl_main.py  # Main ETL logic
│   │   └── python_udfs/sync_to_clickhouse.py
│   ├── k8s/05-ml-pipeline/         # Kubernetes Jobs
│   │   ├── job-ml-train-gpu.yaml   # GPU training job
│   │   ├── job-ml-predict.yaml     # Forecast job
│   │   ├── job-spark-etl.yaml      # Spark ETL job
│   │   └── job-sync.yaml           # PostgreSQL → ClickHouse sync
│   ├── docker/                     # Docker Compose (legacy)
│   └── Makefile                    # Main build commands
│
├── ml-pipeline/models/             # 🧠 Saved models
└── AGENTS.md                       # This file
```

---

## 🛠️ Technology Stack

| Layer | Công nghệ | Mục đích |
|-------|-----------|----------|
| **ETL** | PySpark 3.5, Python 3.11 | Xử lý CSV quy mô lớn |
| **OLTP** | PostgreSQL 15 | Lưu trữ giao dịch |
| **OLAP** | ClickHouse 24 | Data Warehouse, time-series |
| **ML** | XGBoost 2.0, Optuna 3.4 | Dự báo + Hyperparameter tuning |
| **GPU** | CUDA 12.1, PyTorch 2.1 | GPU-accelerated training |
| **Email** | Gmail SMTP | Notifications |
| **Container** | Docker, Kubernetes | Deployment |
| **Orchestration** | K3s CronJobs | Scheduling |

---

## 🚀 Docker Images

| Image | Tag | Mục đích | Size |
|-------|-----|----------|------|
| `annduke/hasu-spark-etl` | `dedup-v1` | PySpark ETL với deduplication | ~4GB |
| `annduke/hasu-ml-pipeline` | `gpu-stable-v2` | GPU training | ~12.9GB |
| `annduke/hasu-ml-pipeline` | `stable-v2` | CPU inference | ~792MB |
| `annduke/hasu-ml-pipeline` | `email-fix-v1` | Fixed email config | ~12.9GB |
| `annduke/hasu-sync-tool` | `dedup-v1` | PostgreSQL → ClickHouse sync | ~500MB |

---

## ⚡ Spark ETL

### Chức năng
- **Process Products**: UPSERT danh sách sản phẩm từ `DanhSachSanPham*.csv/xlsx`
- **Process Sales**: Import báo cáo bán hàng từ `BaoCaoBanHang*.csv/xlsx`
- **Auto-Move**: File đã xử lý tự động chuyển sang `/csv_input/processed/`

### Cơ chế bảo vệ dữ liệu

| Đặc điểm | Mô tả |
|----------|-------|
| **UPSERT ONLY** | `ON CONFLICT DO UPDATE/NOTHING` - Luôn giữ dữ liệu cũ |
| **KHÔNG TRUNCATE** | Không bao giờ xóa toàn bộ bảng |
| **KHÔNG DELETE** | Không xóa dữ liệu cũ, chỉ thêm mới/cập nhật |
| **Logging** | Hiển thị số records trước/sau để xác nhận |

### Usage

```bash
# Docker - UPSERT mode (default - luôn giữ dữ liệu cũ)
docker run --rm -v $(pwd)/csv_input:/csv_input \
  -e POSTGRES_HOST=postgres \
  annduke/hasu-spark-etl:dedup-v1 \
  python etl_main.py

# K8s
kubectl apply -f k8s/05-ml-pipeline/job-spark-etl.yaml
```

### Xử lý file đã xử lý
- File sau khi import thành công sẽ được chuyển sang `/csv_input/processed/`
- Nếu file đã tồn tại ở processed, tự động thêm timestamp: `file_20250325_143022.csv`
- Tránh xử lý lại file cũ khi chạy ETL nhiều lần

---

## ⚡ Quick Commands

### Kiểm tra trạng thái
```bash
# Pods
kubectl get pods -n hasu-ml

# Jobs
kubectl get jobs -n hasu-ml

# CronJobs
kubectl get cronjob -n hasu-ml

# Logs
kubectl logs -n hasu-ml job/ml-training-gpu
```

### Chạy pipeline
```bash
# Full pipeline
make app-k3s DOCKERHUB_USERNAME=annduke

# Chỉ ETL
kubectl apply -f k8s/05-ml-pipeline/job-spark-etl.yaml

# Chỉ training
kubectl create job --from=cronjob/ml-training ml-training-test

# Chỉ forecast
kubectl create job --from=cronjob/ml-predict ml-predict-test
```

### Xử lý lỗi
```bash
# Xóa job stuck
kubectl delete job <job-name> -n hasu-ml --force

# Xóa pod lỗi
kubectl delete pod <pod-name> -n hasu-ml --force

# Check GPU node
kubectl describe node k3s-worker-gpu | grep -i nvidia

# Check resource quota
kubectl describe resourcequota hasu-ml-quota -n hasu-ml
```

---

## 🔧 Cấu hình quan trọng

### Email Notifications
```yaml
# ConfigMap hasu-ml-config
EMAIL_SENDER: nguyenanhduc111203@gmail.com
EMAIL_FORECAST_REPORT: djkieu123@gmail.com
EMAIL_TRAINING_REPORT: djkieu123@gmail.com
EMAIL_ERROR_ALERT: admin@hasu.com

# Secret hasu-ml-secrets
EMAIL_PASSWORD: <gmail-app-password>
```

### GPU Training
```yaml
# job-ml-train-gpu.yaml
resources:
  limits:
    memory: "16Gi"      # Tăng từ 8Gi (OOM fix)
    cpu: "4"
    nvidia.com/gpu: 1
  requests:
    memory: "4Gi"
    cpu: "2"
    nvidia.com/gpu: 1
env:
  - name: USE_GPU
    value: "true"
```

### PVCs
| Name | Node | Mục đích |
|------|------|----------|
| `ml-models` | k3s-master | CPU models |
| `ml-models-gpu` | k3s-worker-gpu | GPU models |
| `csv-input-pvc` | any | CSV input |
| `csv-output-pvc` | any | CSV output |

---

## 🐛 Known Issues & Fixes

### 1. OOMKilled (Exit Code 137)
**Nguyên nhân**: Training cần >8GB RAM  
**Fix**: Tăng memory limit lên 16GB

### 2. Image `gpu-latest` not found
**Nguyên nhân**: Image đã bị xóa  
**Fix**: Dùng `gpu-stable-v2`

### 3. Email sender không phải Gmail
**Nguyên nhân**: `ml-pipeline@hasu.com` không hợp lệ cho smtp.gmail.com  
**Fix**: Cập nhật `EMAIL_SENDER` thành `nguyenanhduc111203@gmail.com`

### 4. Data duplication
**Nguyên nhân**: Sync tool append thay vì replace  
**Fix**: Thêm `TRUNCATE` trước khi sync

### 5. PostgreSQL auth failed
**Nguyên nhân**: Password mismatch  
**Fix**: Đồng bộ password với secret

### 6. Node affinity conflict (GPU)
**Nguyên nhân**: PVC `ml-models` ở master, GPU ở worker  
**Fix**: Tạo `ml-models-gpu` trên worker node

---

## 📊 Pipeline Flow

```
CSV Input
    ↓
PySpark ETL (spark-etl) ──→ PostgreSQL (OLTP)
    ↓                            ↓
Sync Tool ───────────────────→ ClickHouse (OLAP)
    ↓
DBT Transform
    ↓
ML Training (GPU) ──→ XGBoost Models ──→ ML Predict
    ↓                                      ↓
Email Report                          Email Forecast
    ↓                                      ↓
PostgreSQL                           PostgreSQL
    ↓
Superset Dashboard
```

---

## 📝 Coding Conventions

1. **Ngôn ngữ**: Tiếng Việt cho comments, tên biến có ý nghĩa
2. **Logging**: Dùng `logging` module, format `%(asctime)s - %(levelname)s - %(message)s`
3. **GPU Check**: Luôn kiểm tra `nvidia-smi` trước khi dùng GPU
4. **Error Handling**: Try-except với logger.error
5. **Email**: Gửi report sau mỗi training/predict

---

## 🔗 Useful Links

- K3s Dashboard: `kubectl get nodes`
- Airflow: Port 30080
- Superset: Port 30088
- Grafana (nếu có): Port 31300

---

## 👤 Contact

- Email: djkieu123@gmail.com
- Dev: nguyenanhduc111203@gmail.com
