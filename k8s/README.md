# K3s Deployment for Hasu ML

Triển khai Retail Data Pipeline trên **K3s cluster** với CI/CD tự động từ GitHub Actions.

> 🎯 **Mục đích**: Deploy thực tế, production, auto-scaling
> 
> 💻 **Development**: Xem [docker/README.md](../docker/README.md) để chạy local

---

## 📋 Yêu cầu hệ thống

| Resource | Tối thiểu | Khuyến nghị |
|----------|-----------|-------------|
| OS | Ubuntu 20.04/22.04 LTS | Ubuntu 22.04 LTS |
| RAM | 8GB | 16GB+ |
| CPU | 4 cores | 8 cores+ |
| Disk | 50GB SSD | 100GB+ SSD |
| Network | Internet connection | Static IP + Domain |

---

## 🏗️ Kiến trúc triển khai

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

---

## 🚀 Quick Start

### Bước 1: Cài đặt K3s

```bash
curl -sfL https://get.k3s.io | sh -

# Kiểm tra cài đặt
sudo kubectl get nodes
sudo kubectl get pods -n kube-system
```

### Bước 2: Cấu hình GitHub Secrets

Vào **GitHub Repository → Settings → Secrets and variables → Actions**, thêm:

| Secret | Mô tả | Ví dụ |
|--------|-------|-------|
| `DOCKERHUB_USERNAME` | Username Docker Hub | `annduke128` |
| `DOCKERHUB_TOKEN` | Access Token Docker Hub | `dckr_pat_xxx` |
| `POSTGRES_PASSWORD` | Mật khẩu PostgreSQL | `secure_password` |
| `CLICKHOUSE_PASSWORD` | Mật khẩu ClickHouse | `secure_password` |

### Bước 3: Setup Self-Hosted Runner

Chạy trên K3s server (với quyền root để tránh vấn đề kubeconfig):

```bash
# Tạo thư mục cho runner
mkdir -p /root/actions-runner && cd /root/actions-runner

# Download runner (thay phiên bản mới nhất nếu cần)
curl -o actions-runner-linux-x64-2.311.0.tar.gz \
  -L https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz
tar xzf actions-runner-linux-x64-2.311.0.tar.gz

# Cấu hình (thay YOUR_TOKEN bằng token từ GitHub Actions settings)
./config.sh --url https://github.com/YOUR_USERNAME/YOUR_REPO --token YOUR_TOKEN

# Chạy runner
./run.sh

# (Optional) Cài đặt như service để tự động chạy
sudo ./svc.sh install
sudo ./svc.sh start
```

### Bước 4: Triển khai lần đầu

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

### Bước 5: Chạy pipeline trên K3s

```bash
# Chạy full pipeline
make app-k3s DOCKERHUB_USERNAME=yourusername

# Hoặc chạy từng bước riêng lẻ
make k3s-sync        # Chỉ chạy sync
make k3s-dbt         # Chỉ chạy DBT
make k3s-ml-train    # Chỉ train model
make k3s-ml-predict  # Chỉ predict
```

---

## 📁 Cấu trúc thư mục

```
k8s/
├── 00-namespace/          # Namespace và Network Policies
│   ├── namespace.yaml
│   └── network-policy.yaml
├── 01-storage/            # StorageClass và PVCs
│   ├── storage-class.yaml
│   ├── postgres-pvc.yaml
│   ├── clickhouse-pvc.yaml
│   └── ml-models-pvc.yaml
├── 02-config/             # ConfigMaps và Secrets
│   ├── configmap.yaml
│   └── secrets-template.yaml  # Copy thành secrets.yaml
├── 03-databases/          # PostgreSQL, ClickHouse, Redis
│   ├── postgres.yaml
│   ├── clickhouse.yaml
│   └── redis.yaml
├── 04-applications/       # Airflow, Superset
│   ├── airflow.yaml
│   └── superset.yaml
├── 05-ml-pipeline/        # ML Training và Prediction
│   ├── cronjob-training.yaml
│   ├── cronjob-predict.yaml
│   ├── job-sync.yaml
│   ├── job-dbt-build.yaml
│   ├── job-ml-train.yaml
│   └── job-ml-predict.yaml
├── scripts/               # Helper scripts
│   ├── install-k3s.sh
│   ├── build-and-push.sh
│   ├── deploy-all.sh
│   ├── status-check.sh
│   └── auto-update.sh
└── README.md              # This file
```

---

## 📊 Truy cập Services

| Service | URL | Port | Credentials |
|---------|-----|------|-------------|
| Airflow | http://node-ip:30080 | 30080 | admin / admin |
| Superset | http://node-ip:30088 | 30088 | admin / admin |
| PostgreSQL | ClusterIP | 5432 | retail_user / (from secret) |
| ClickHouse | ClusterIP | 8123 | default / (from secret) |

### Port Forward (để truy cập local)

```bash
# PostgreSQL
kubectl port-forward svc/postgres 5432:5432 -n hasu-ml

# ClickHouse
kubectl port-forward svc/clickhouse 8123:8123 -n hasu-ml

# Airflow
kubectl port-forward svc/airflow 8080:8080 -n hasu-ml

# Superset
kubectl port-forward svc/superset 8088:8088 -n hasu-ml
```

---

## 🔄 Tự động cập nhật từ DockerHub

### Phương pháp 1: GitHub Actions (Khuyến nghị)

Mỗi push lên `main` sẽ tự động:
1. Build images mới
2. Push lên Docker Hub
3. Deploy lên K3s

### Phương pháp 2: Manual Update

```bash
# Chạy script cập nhật
./k8s/scripts/auto-update.sh your-dockerhub-username
```

### Phương pháp 3: ImagePullPolicy Always

Các CronJobs đã được cấu hình `imagePullPolicy: Always` nên sẽ tự động pull latest image mỗi lần chạy.

---

## 🛠️ Troubleshooting

### Pod không start

```bash
# Check logs
kubectl logs -f deployment/postgres -n hasu-ml
kubectl logs -f deployment/clickhouse -n hasu-ml

# Check events
kubectl get events -n hasu-ml --sort-by='.lastTimestamp'

# Describe pod
kubectl describe pod <pod-name> -n hasu-ml
```

### PVC pending

```bash
# Check storage class
kubectl get sc

# Check PVC status
kubectl get pvc -n hasu-ml
kubectl describe pvc <pvc-name> -n hasu-ml
```

### Image pull failed

```bash
# Check dockerhub credentials
kubectl get secret dockerhub-credentials -n hasu-ml -o yaml

# Re-apply secrets (từ GitHub Actions hoặc manually)
kubectl apply -f k8s/02-config/secrets.yaml
```

### Self-hosted runner không chạy

```bash
# Kiểm tra runner status
cd ~/actions-runner
./svc.sh status

# Xem logs
sudo journalctl -u actions.runner.* -f

# Restart runner
sudo ./svc.sh stop
sudo ./svc.sh start
```

---

## 🔧 Useful Commands

### Root Makefile

```bash
# Deploy
make k8s-deploy-all     # Full deployment
make k8s-deploy         # Update images only

# Run pipeline
make app-k3s            # Run full pipeline
make k3s-sync           # Sync only
make k3s-dbt            # DBT only
make k3s-ml-train       # ML train only
make k3s-ml-predict     # ML predict only

# Status
make k8s-status         # Check all resources
make k8s-logs           # View logs

# Delete
make k8s-delete         # Delete namespace (⚠️ mất dữ liệu)
```

### kubectl Commands

```bash
# Get resources
kubectl get all -n hasu-ml
kubectl get pods -n hasu-ml
kubectl get jobs -n hasu-ml
kubectl get cronjobs -n hasu-ml
kubectl get pvc -n hasu-ml

# Logs
kubectl logs -n hasu-ml deployment/postgres
kubectl logs -n hasu-ml job/sync-data
kubectl logs -n hasu-ml job/dbt-build
kubectl logs -n hasu-ml job/ml-train

# Execute
kubectl exec -it -n hasu-ml deployment/postgres -- psql -U retail_user -d retail_db
kubectl exec -it -n hasu-ml deployment/clickhouse -- clickhouse-client

# Port forward
kubectl port-forward svc/airflow 8080:8080 -n hasu-ml &
kubectl port-forward svc/superset 8088:8088 -n hasu-ml &

# Scale
kubectl scale deployment airflow-webserver --replicas=2 -n hasu-ml

# Rollback
kubectl rollout undo deployment/airflow-webserver -n hasu-ml

# Delete namespace (⚠️ XÓA TẤT CẢ)
kubectl delete namespace hasu-ml
```

---

## 📝 Lưu ý quan trọng

1. **Không commit secrets.yaml** - File này chứa thông tin nhạy cảm
2. **Self-hosted runner** - Chạy với quyền root để tránh vấn đề kubeconfig
3. **Backup dữ liệu** - PVCs không được backup tự động
4. **Resource limits** - Điều chỉnh limits trong YAML files theo hardware
5. **ImagePullPolicy** - Luôn dùng `Always` cho production

---

## 🔄 So sánh với Docker Compose

| Tiêu chí | Docker Compose | K3s |
|----------|---------------|-----|
| **Mục đích** | Dev/Test | Production |
| **Độ phức tạp** | Thấp | Cao |
| **CI/CD** | Manual | GitHub Actions |
| **High Availability** | Không | Có |
| **Multi-node** | Không | Có |
| **Auto-scaling** | Không | Có |
| **SSL/TLS** | Manual | Cert-manager |

👉 **Development/Testing**: Xem [docker/README.md](../docker/README.md)

---

## 📚 Tài liệu liên quan

- [Root README.md](../README.md) - Tổng quan dự án
- [AGENTS.md](../AGENTS.md) - Hướng dẫn cho AI agents
- [docker/README.md](../docker/README.md) - Chạy local với Docker
