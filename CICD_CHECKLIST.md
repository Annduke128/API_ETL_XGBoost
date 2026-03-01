# CI/CD Pipeline Checklist - Docker Hub & GitHub Actions

Hướng dẫn chi tiết để thiết lập CI/CD pipeline cho Hasu ML Project.

---

## ✅ 1. DOCKER HUB SETUP

### 1.1 Tạo Docker Hub Account
- [ ] Truy cập https://hub.docker.com và đăng ký tài khoản
- [ ] Xác nhận email
- [ ] Tạo Organization (tùy chọn) hoặc dùng personal account

### 1.2 Tạo Access Token
- [ ] Đăng nhập Docker Hub → Account Settings → Security
- [ ] Click "New Access Token"
- [ ] Đặt tên: `github-actions` hoặc `ci-cd-token`
- [ ] Quyền: `Read, Write, Delete`
- [ ] **COPY TOKEN NGAY** (chỉ hiển thị 1 lần)

### 1.3 Tạo Repositories
Tạo 3 repositories trên Docker Hub:
- [ ] `hasu-ml-pipeline` (Public hoặc Private)
- [ ] `hasu-dbt` (Public hoặc Private)
- [ ] `hasu-sync-tool` (Public hoặc Private)

---

## ✅ 2. GITHUB SETUP

### 2.1 Repository Secrets
Vào GitHub Repo → Settings → Secrets and variables → Actions → New repository secret

| Secret Name | Value | Mô tả |
|-------------|-------|-------|
| `DOCKERHUB_USERNAME` | your-dockerhub-username | Tên Docker Hub |
| `DOCKERHUB_TOKEN` | dckr_pat_xxxxx... | Access Token đã tạo ở trên |
| `KUBECONFIG` | (base64 encoded) | Kubeconfig cho K3s (nếu deploy tự động) |

### 2.2 Cách lấy KUBECONFIG cho K3s
```bash
# Trên máy K3s server
cat ~/.kube/config | base64 -w 0

# Copy output và paste vào GitHub Secret "KUBECONFIG"
```

---

## ✅ 3. PROJECT STRUCTURE VERIFICATION

### 3.1 Dockerfiles (✅ Đã có sẵn)
```
docker/
├── ml_pipeline/Dockerfile      ✅ Build context: root (.)
├── dbt_retail/Dockerfile       ✅ Build context: root (.)
└── data_cleaning/Dockerfile    ✅ Build context: root (.)
```

### 3.2 GitHub Actions Workflows (✅ Đã có sẵn)
```
.github/workflows/
├── docker-build-push.yml    ✅ Build & push images
├── deploy-k3s.yml           ✅ Deploy to K3s
└── test.yml                 ✅ Test & lint code
```

### 3.3 K8s Manifests (✅ Đã có sẵn)
```
k8s/
├── 00-namespace/
├── 01-storage/
├── 02-config/
├── 03-databases/
├── 04-applications/
├── 05-ml-pipeline/
└── scripts/
```

---

## ✅ 4. CI/CD WORKFLOW

### 4.1 Build Pipeline
```
Push code to GitHub
    ↓
Trigger: docker-build-push.yml
    ↓
Build 3 images:
  - hasu-ml-pipeline
  - hasu-dbt
  - hasu-sync-tool
    ↓
Push to Docker Hub with tags:
  - latest (main branch)
  - v1.0.0 (git tags)
  - sha-abc123 (commit sha)
```

### 4.2 Deploy Pipeline (Tùy chọn)
```
Build thành công
    ↓
Trigger: deploy-k3s.yml
    ↓
Update K3s CronJobs & Deployments
    ↓
Pull new images from Docker Hub
```

---

## ✅ 5. LOCAL TESTING (Trước khi push)

### 5.1 Test Build Local
```bash
cd Hasu_ML_k3s

# Build từng image
docker build -t test-ml -f docker/ml_pipeline/Dockerfile .
docker build -t test-dbt -f docker/dbt_retail/Dockerfile .
docker build -t test-sync -f docker/data_cleaning/Dockerfile .

# Hoặc dùng script
./k8s/scripts/build-and-push.sh your-username
```

### 5.2 Test Docker Hub Login
```bash
docker login -u your-username
# Nhập password (Access Token)

# Kiểm tra
docker info | grep Username
```

---

## ✅ 6. KIỂM TRA SAU KHI SETUP

### 6.1 Trigger Test Build
```bash
# Cách 1: Push code lên main branch
git push origin main

# Cách 2: Tạo tag mới
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0

# Cách 3: Manual trigger
# Vào GitHub → Actions → Docker Build and Push → Run workflow
```

### 6.2 Kiểm tra Docker Hub
- [ ] 3 images đã được push
- [ ] Tags: `latest`, `v1.0.0`, `sha-xxxxx`

### 6.3 Kiểm tra K3s (nếu dùng auto-deploy)
```bash
# Trên K3s server
kubectl get cronjobs -n hasu-ml
kubectl get deployments -n hasu-ml
kubectl get pods -n hasu-ml
```

---

## ✅ 7. TROUBLESHOOTING

### Build Failed
```bash
# Kiểm tra logs trong GitHub Actions
# Thường do:
# - Thiếu secrets
# - Dockerfile syntax error
# - Network issues
```

### Push Failed
```bash
# Kiểm tra Docker Hub token
# Kiểm tra repository name trong workflow
```

### Deploy Failed
```bash
# Kiểm tra KUBECONFIG
# Kiểm tra K3s cluster accessible
# Kiểm tra namespace tồn tại
```

---

## 📋 SUMMARY

Sau khi hoàn thành checklist:
1. ✅ Docker Hub account + 3 repositories
2. ✅ GitHub Secrets (DOCKERHUB_USERNAME, DOCKERHUB_TOKEN, KUBECONFIG)
3. ✅ Push code → Auto build → Auto push to Docker Hub
4. ✅ (Tùy chọn) Auto deploy to K3s

---

**Last Updated:** 2026-02-28
