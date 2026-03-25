# Retail ML Pipeline - Hệ thống Dự báo Bán hàng

Hệ thống Machine Learning pipeline hoàn chỉnh cho ngành bán lẻ với XGBoost forecasting, GPU acceleration, và email notifications.

---

## 📋 Mục lục

1. [Tổng quan](#-tổng-quan)
2. [Kiến trúc hệ thống](#-kiến-trúc-hệ-thống)
3. [Triển khai](#-triển-khai)
4. [Cấu hình](#-cấu-hình)
5. [Troubleshooting](#-troubleshooting)

---

## 🎯 Tổng quan

**Retail ML Pipeline** cung cấp:

- 📊 **ETL**: PySpark xử lý CSV quy mô lớn
- 🗄️ **Data Warehouse**: PostgreSQL + ClickHouse
- 🤖 **ML Forecasting**: XGBoost với GPU support
- 📧 **Email Reports**: Training & Forecast notifications
- 📈 **BI Dashboard**: Apache Superset

### Thành phần chính

| Service | Port | Mô tả |
|---------|------|-------|
| PostgreSQL | 5432 | OLTP Database |
| ClickHouse | 8123/9000 | Data Warehouse |
| Redis | 6379 | Cache & Buffer |
| Airflow | 30080 | Workflow Scheduler |
| Superset | 30088 | BI Dashboard |
| Spark Master | 30081 | Spark UI |

---

## 🏗️ Kiến trúc hệ thống

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│  CSV Input  │────▶│  Spark ETL  │────▶│  PostgreSQL     │
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
   │   DBT    │   │  ML/XGB  │                            │ Superset │
   │Transform │   │  (GPU)   │                            │   (BI)   │
   └──────────┘   └──────────┘                            └──────────┘
         │                                               ▲
         └──────────────────┬────────────────────────────┘
                            ▼
                     ┌──────────────┐
                     │   Airflow    │
                     │ (Scheduler)  │
                     └──────────────┘
```

---

## 🚀 Triển khai

### Yêu cầu

| Resource | Tối thiểu | Khuyến nghị |
|----------|-----------|-------------|
| RAM | 16GB | 32GB+ |
| Disk | 50GB | 100GB+ SSD |
| GPU | 1x NVIDIA | RTX 3060+ |
| K3s | 2 nodes | 3 nodes |

### Quick Start

```bash
# 1. Chạy full pipeline
make app-k3s DOCKERHUB_USERNAME=annduke

# 2. Kiểm tra trạng thái
kubectl get pods -n hasu-ml

# 3. Xem logs
kubectl logs -f -n hasu-ml job/ml-training-gpu

# 4. Truy cập dashboard
# Airflow: http://<node-ip>:30080
# Superset: http://<node-ip>:30088
```

### Chạy từng phần

```bash
# ETL only - UPSERT mode (luôn giữ dữ liệu cũ)
kubectl apply -f k8s/05-ml-pipeline/job-spark-etl.yaml

# Training only (GPU)
kubectl create job --from=cronjob/ml-training ml-training-test

# Forecast only
kubectl create job --from=cronjob/ml-predict ml-predict-test

# DBT only
kubectl apply -f k8s/05-ml-pipeline/job-dbt-build.yaml
```

---

## ⚙️ Cấu hình

### Email Notifications

```bash
# ConfigMap
kubectl edit configmap hasu-ml-config -n hasu-ml

# Các biến quan trọng:
EMAIL_SENDER=nguyenanhduc111203@gmail.com
EMAIL_FORECAST_REPORT=djkieu123@gmail.com
EMAIL_TRAINING_REPORT=djkieu123@gmail.com
EMAIL_ERROR_ALERT=admin@hasu.com

# Secret (password)
kubectl edit secret hasu-ml-secrets -n hasu-ml
# EMAIL_PASSWORD: <base64-encoded-gmail-app-password>
```

### GPU Training

```bash
# Job template: k8s/05-ml-pipeline/job-ml-train-gpu.yaml
resources:
  limits:
    memory: "16Gi"      # Tăng nếu OOM
    cpu: "4"
    nvidia.com/gpu: 1
  requests:
    memory: "4Gi"
    cpu: "2"
    nvidia.com/gpu: 1
```

### CronJob Schedule

| Job | Schedule | Mục đích |
|-----|----------|----------|
| `ml-training` | `0 2 * * 0` | Training hàng tuần (Chủ nhật 2AM) |
| `ml-predict` | `0 6 * * *` | Forecast hàng ngày (6AM) |
| `dbt-daily` | `0 3 * * *` | DBT build hàng ngày (3AM) |

---

## 🔧 Troubleshooting

### 1. Job bị OOMKilled (Exit Code 137)

```bash
# Tăng memory limit
kubectl patch job <job-name> -n hasu-ml --type='json' \
  -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value":"16Gi"}]'
```

### 2. Image không tìm thấy

```bash
# Kiểm tra image tags
docker pull annduke/hasu-ml-pipeline:gpu-stable-v2

# Cập nhật cronjob
kubectl patch cronjob ml-training -n hasu-ml --type='json' \
  -p='[{"op": "replace", "path": "/spec/jobTemplate/spec/template/spec/containers/0/image", "value":"annduke/hasu-ml-pipeline:gpu-stable-v2"}]'
```

### 3. GPU node không schedule được

```bash
# Kiểm tra node labels
kubectl get nodes -l nvidia.com/gpu.present=true

# Tạo PVC trên GPU node
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ml-models-gpu
  namespace: hasu-ml
spec:
  accessModes: ["ReadWriteOnce"]
  storageClassName: local-storage
  resources:
    requests:
      storage: 20Gi
EOF
```

### 4. Lỗi gửi email

```bash
# Kiểm tra email config
kubectl exec -n hasu-ml deployment/airflow-scheduler -- env | grep EMAIL

# Test email
kubectl create job test-email -n hasu-ml --image=annduke/hasu-ml-pipeline:email-fix-v1 \
  -- python -c "from email_notifier import get_notifier; n = get_notifier(); print(n._get_recipients('forecast_report'))"
```

### 5. Data duplication

```bash
# Dọn dẹp PostgreSQL
kubectl exec postgres-587844c956-fj9kc -n hasu-ml -- psql -U retail_user -d retail_db -c "
DELETE FROM transaction_details WHERE id NOT IN (
    SELECT MIN(id) FROM transaction_details GROUP BY giao_dich_id, product_id
);"

# Truncate ClickHouse
kubectl exec clickhouse-5f8f5b445c-stk6p -n hasu-ml -- clickhouse-client --query "TRUNCATE TABLE staging_products"
```

### 6. PostgreSQL auth failed

```bash
# Đồng bộ password
NEW_PASS=$(kubectl get secret hasu-ml-secrets -n hasu-ml -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)
kubectl exec postgres-587844c956-fj9kc -n hasu-ml -- psql -U postgres -c "ALTER USER retail_user WITH PASSWORD '$NEW_PASS';"
```

---

## 📊 Monitoring

```bash
# Resource usage
kubectl top pods -n hasu-ml

# GPU usage
kubectl exec -n hasu-ml <gpu-pod> -- nvidia-smi

# Logs
kubectl logs -f -n hasu-ml -l app=ml-training

# Events
kubectl get events -n hasu-ml --sort-by='.lastTimestamp' | tail -20
```

---

## 🐳 Docker Images

| Image | Version | Mục đích |
|-------|---------|----------|
| annduke/hasu-spark-etl | dedup-v1 | PySpark ETL |
| annduke/hasu-ml-pipeline | gpu-stable-v2 | GPU training |
| annduke/hasu-ml-pipeline | stable-v2 | CPU inference |
| annduke/hasu-ml-pipeline | email-fix-v1 | Fixed email |
| annduke/hasu-sync-tool | dedup-v1 | DB sync |
| annduke/hasu-dbt | latest | DBT transform |

---

## 👥 Liên hệ

- **Email**: djkieu123@gmail.com
- **Dev**: nguyenanhduc111203@gmail.com

---

## 📄 License

Private - For internal use only.
