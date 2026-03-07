# DockerHub & CI/CD Pipeline Guide

Hướng dẫn đầy đủ cho việc sử dụng DockerHub và CI/CD với GitHub Actions.

---

## 📋 Mục lục

1. [DockerHub Setup](#1-dockerhub-setup)
2. [Local Build & Push](#2-local-build--push)
3. [GitHub Actions CI/CD](#3-github-actions-cicd)
4. [K3s Auto-Update](#4-k3s-auto-update)
5. [Troubleshooting](#5-troubleshooting)

---

## 1. DockerHub Setup

### 1.1 Tạo tài khoản DockerHub

1. Truy cập https://hub.docker.com
2. Đăng ký tài khoản miễn phí
3. Xác nhận email

### 1.2 Tạo Access Token

1. Đăng nhập DockerHub
2. Vào **Account Settings** → **Security**
3. Click **New Access Token**
4. Đặt tên: `hasu-ml-ci-cd`
5. Quyền: `Read, Write, Delete`
6. Copy token (chỉ hiện 1 lần!)

### 1.3 Thiết lập GitHub Secrets

Vào repository GitHub → **Settings** → **Secrets and variables** → **Actions**:

| Secret Name | Value | Mô tả |
|-------------|-------|-------|
| `DOCKERHUB_USERNAME` | your-username | Tên DockerHub |
| `DOCKERHUB_TOKEN` | dckr_pat_xxx... | Access Token |
| `KUBECONFIG` | base64_encoded... | Kubeconfig K3s |

#### Encode Kubeconfig:

```bash
# Trên K3s server
cat ~/.kube/config | base64 -w 0

# Copy output và paste vào GitHub Secret `KUBECONFIG`
```

---

## 2. Local Build & Push

### 2.1 Cách thủ công

```bash
# Đăng nhập DockerHub
docker login -u your-username

# Build images (từ service folders)
docker build -t your-username/hasu-sync-tool:latest ./data_cleaning
docker build -t your-username/hasu-ml-pipeline:latest ./ml_pipeline
docker build -t your-username/hasu-spark-etl:latest ./spark-etl
docker build -t your-username/hasu-dbt:latest ./dbt_retail

# Push images
docker push your-username/hasu-sync-tool:latest
docker push your-username/hasu-ml-pipeline:latest
docker push your-username/hasu-spark-etl:latest
docker push your-username/hasu-dbt:latest
```

**Lưu ý về Build Context:**
Mỗi service được build từ folder riêng của nó (không phải từ root):

| Image | Build Context | Dockerfile |
|-------|---------------|------------|
| `hasu-sync-tool` | `./data_cleaning` | `data_cleaning/Dockerfile` |
| `hasu-ml-pipeline` | `./ml_pipeline` | `ml_pipeline/Dockerfile` |
| `hasu-spark-etl` | `./spark-etl` | `spark-etl/Dockerfile` |
| `hasu-dbt` | `./dbt_retail` | `dbt_retail/Dockerfile` |

### 2.2 Cách tự động (Script)

```bash
# Sử dụng script có sẵn ở root
./build-and-push-k3s.sh your-username

# Script sẽ tự động build tất cả 4 images từ các service folders
# và push lên DockerHub với tag `latest`
```

### 2.3 Pull images

```bash
# Pull về local
docker pull your-username/hasu-ml-pipeline:latest

# Hoặc trên K3s (đã có imagePullPolicy: Always)
# Images tự động pull khi deploy/restart
```

---

## 3. GitHub Actions CI/CD

### 3.1 Các Workflows

| Workflow | File | Trigger | Mô tả |
|----------|------|---------|-------|
| Test & Lint | `.github/workflows/test.yml` | Push/PR | Kiểm tra code |
| Build & Push | `.github/workflows/docker-build-push.yml` | Push/Tag | Build & push images |
| Deploy K3s | `.github/workflows/deploy-k3s.yml` | Sau build | Auto deploy K3s |

### 3.2 Quy trình tự động

```
Push code → Test & Lint → Build Images → Push DockerHub → Deploy K3s
    │              │            │              │              │
    └──────────────┴────────────┴──────────────┴──────────────┘
                    GitHub Actions
```

### 3.3 Tags và Versions

| Git Tag | Docker Tag | Mô tả |
|---------|------------|-------|
| `v1.2.3` | `1.2.3`, `1.2`, `latest` | Release version |
| `main` branch | `main`, `latest` | Latest stable |
| `develop` branch | `develop` | Development |
| PR | `pr-123` | Pull request |

### 3.4 Tạo Release mới

```bash
# Tạo tag
git tag -a v1.0.0 -m "Release version 1.0.0"

# Push tag (trigger CI/CD)
git push origin v1.0.0
```

### 3.5 Manual Trigger

Vào **Actions** tab → Chọn workflow → **Run workflow**:

- **Build & Push**: Chạy thủ công
- **Deploy K3s**: Chọn environment

---

## 4. K3s Auto-Update

### 4.1 Cách 1: Auto-update trong K3s (Khuyến nghị)

CronJobs đã cấu hình `imagePullPolicy: Always`:

```yaml
image: your-username/hasu-ml-pipeline:latest
imagePullPolicy: Always  # Luôn pull image mới
```

Mỗi lần CronJob chạy sẽ tự động pull image mới nhất.

### 4.2 Cách 2: GitHub Actions Auto-deploy

Khi push lên `main`, workflow `deploy-k3s.yml` tự động:
1. Cập nhật image tags
2. Restart deployments
3. Kiểm tra rollout status

### 4.3 Cách 3: Script manual update

```bash
# Trên K3s server
./k8s/scripts/auto-update.sh your-username
```

### 4.4 Cách 4: Watchtower (External tool)

```yaml
# Optional: Deploy Watchtower để auto-update
apiVersion: apps/v1
kind: Deployment
metadata:
  name: watchtower
spec:
  template:
    spec:
      containers:
      - name: watchtower
        image: containrrr/watchtower
        env:
        - name: WATCHTOWER_POLL_INTERVAL
          value: "3600"  # Check every hour
```

---

## 5. Troubleshooting

### 5.1 DockerHub Login Failed

```bash
# Kiểm tra đăng nhập
docker info | grep Username

# Nếu chưa login
docker logout && docker login

# Kiểm tra token hết hạn
# Tạo lại token trên DockerHub nếu cần
```

### 5.2 Build Failed

```bash
# Build với chi tiết lỗi (từ service folder)
docker build --progress=plain ./ml_pipeline

# Kiểm tra Dockerfile
docker run --rm -i hadolint/hadolint < ml_pipeline/Dockerfile
```

### 5.3 K3s Image Pull Failed

```bash
# Kiểm tra secret
dockerhub-credentials
kubectl get secret dockerhub-credentials -n hasu-ml -o yaml

# Xem log
docker pull your-username/hasu-ml-pipeline:latest
```

### 5.4 CI/CD Failed

1. Vào **Actions** tab
2. Click vào workflow bị lỗi
3. Xem chi tiết step bị lỗi

Common issues:
- Secrets chưa set đúng
- Quyền repository không đủ
- Dockerfile syntax error

---

## 📝 Best Practices

### 1. Versioning

```bash
# Luôn tag version
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

### 2. Multi-arch Images (AMD64/ARM64)

```yaml
# Thêm vào workflow
platforms: linux/amd64,linux/arm64
```

### 3. Security Scanning

```yaml
# Thêm vào workflow
- name: Scan image
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: your-image:latest
```

### 4. Cache Optimization

```yaml
# Đã có trong workflow
cache-from: type=gha
cache-to: type=gha,mode=max
```

---

## 🔗 Useful Commands

```bash
# Xem images trên DockerHub
docker search your-username

# Xem tags
docker pull your-username/hasu-ml-pipeline:tagname

# Remove local images
docker rmi $(docker images -q your-username/hasu-ml-pipeline)

# Xem history
docker history your-username/hasu-ml-pipeline:latest
```

---

*Last updated: 2026-03-07*

---

## 📁 Build Context Structure

### Thay đổi gần đây (2026-03-07)

Đã dọn dẹp cấu trúc Docker để tránh trùng lặp:

**Đã xóa:**
- `docker/data_cleaning/` → Dùng `data_cleaning/` trực tiếp
- `docker/ml_pipeline/` → Dùng `ml_pipeline/` trực tiếp  
- `docker/dbt_retail/` → Dùng `dbt_retail/` trực tiếp
- Các `Dockerfile.*` ở root (trùng lặp)

**Lợi ích:**
- Giảm trùng lặp code
- Build context rõ ràng hơn
- Không còn lỗi `COPY requirements.txt . not found` trong CI/CD
- Dễ bảo trì hơn
