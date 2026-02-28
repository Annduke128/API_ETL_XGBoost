# K3s Deployment for Hasu ML

Triển khai Retail Data Pipeline trên K3s cluster với tự động cập nhật từ DockerHub.

## 📋 Yêu cầu

- **OS**: Ubuntu 20.04/22.04 LTS
- **RAM**: Tối thiểu 8GB (khuyến nghị 16GB)
- **Disk**: 50GB+ SSD
- **Network**: Internet connection để pull images

## 🚀 Quick Start

### 1. Cài đặt K3s

```bash
cd k8s/scripts
./install-k3s.sh
```

### 2. Cấu hình DockerHub

```bash
# Copy template
cp k8s/02-config/secrets-template.yaml k8s/02-config/secrets.yaml

# Edit secrets.yaml với thông tin của bạn
nano k8s/02-config/secrets.yaml

# Apply secrets
kubectl apply -f k8s/02-config/secrets.yaml
```

### 3. Build và Push Images

```bash
# Đăng nhập DockerHub
docker login

# Build và push
cd k8s/scripts
./build-and-push.sh your-dockerhub-username
```

### 4. Deploy toàn bộ hệ thống

```bash
cd k8s/scripts
./deploy-all.sh
```

### 5. Kiểm tra status

```bash
./status-check.sh
```

## 📁 Cấu trúc thư mục

```
k8s/
├── 00-namespace/          # Namespace và Network Policies
├── 01-storage/            # StorageClass và PVCs
├── 02-config/             # ConfigMaps và Secrets
├── 03-databases/          # PostgreSQL, ClickHouse, Redis
├── 04-applications/       # Airflow, Superset
├── 05-ml-pipeline/        # ML Training và Prediction CronJobs
└── scripts/               # Helper scripts
```

## 🔄 Tự động cập nhật từ DockerHub

### Phương pháp 1: Manual Update

```bash
# Chạy script cập nhật
./k8s/scripts/auto-update.sh your-dockerhub-username
```

### Phương pháp 2: Auto-update CronJob trong K3s

Tạo một CronJob để tự động cập nhật hàng ngày:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: auto-updater
  namespace: hasu-ml
spec:
  schedule: "0 */6 * * *"  # Every 6 hours
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: auto-updater
          containers:
          - name: updater
            image: bitnami/kubectl:latest
            command:
            - /bin/sh
            - -c
            - |
              kubectl rollout restart deployment/airflow-webserver -n hasu-ml
              kubectl rollout restart deployment/airflow-scheduler -n hasu-ml
              kubectl rollout restart deployment/superset -n hasu-ml
          restartPolicy: OnFailure
```

### Phương pháp 3: ImagePullPolicy Always

Các CronJobs đã được cấu hình `imagePullPolicy: Always` nên sẽ tự động pull latest image mỗi lần chạy.

## 📊 Truy cập Services

| Service | URL | Port |
|---------|-----|------|
| Airflow | http://node-ip:30080 | 30080 |
| Superset | http://node-ip:30088 | 30088 |
| PostgreSQL | localhost:5432 (port-forward) | 5432 |
| ClickHouse | localhost:8123 (port-forward) | 8123 |

## 🛠️ Troubleshooting

### Pod không start

```bash
# Check logs
kubectl logs -f deployment/postgres -n hasu-ml
kubectl logs -f deployment/clickhouse -n hasu-ml

# Check events
kubectl get events -n hasu-ml --sort-by='.lastTimestamp'
```

### PVC pending

```bash
# Check storage class
kubectl get sc

# Check PVC status
kubectl get pvc -n hasu-ml
```

### Image pull failed

```bash
# Check dockerhub credentials
kubectl get secret dockerhub-credentials -n hasu-ml -o yaml

# Re-apply secrets
kubectl apply -f k8s/02-config/secrets.yaml
```

## 📝 Lưu ý quan trọng

1. **Không commit secrets.yaml** - File này chứa thông tin nhạy cảm
2. **Backup dữ liệu** - PVCs không được backup tự động
3. **Resource limits** - Điều chỉnh limits theo hardware của bạn

## 🔗 Useful Commands

```bash
# Port forward để truy cập local
kubectl port-forward svc/airflow 8080:8080 -n hasu-ml &
kubectl port-forward svc/superset 8088:8088 -n hasu-ml &

# Scale deployment
kubectl scale deployment airflow-webserver --replicas=2 -n hasu-ml

# Rollback deployment
kubectl rollout undo deployment/airflow-webserver -n hasu-ml

# Delete namespace (XÓA TẤT CẢ DỮ LIỆU)
kubectl delete namespace hasu-ml
```
