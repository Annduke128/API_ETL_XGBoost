# ⚠️ Spark Cluster đã chuyển sang hasu-ml namespace

**Ngày cập nhật:** 2026-03-10

## 🚨 Quan trọng

Toàn bộ Spark cluster (Master + Worker) đã được **chuyển sang namespace `hasu-ml`**.

Các file YAML trong `k8s/spark/` có thể **outdated** và không nên được apply trực tiếp.

## 📁 Files hiện tại (trong hasu-ml)

| Component | Namespace | Status |
|-----------|-----------|--------|
| Spark Master | hasu-ml | ✅ Running |
| Spark Worker | hasu-ml | ✅ Running |
| Spark ETL Job | hasu-ml | ✅ Running |

## 🔧 Cấu hình hiện tại

### Spark Master URL
```
spark://spark-master:7077
```
> Lưu ý: Không cần IP hay cross-namespace DNS nữa vì tất cả đều trong `hasu-ml`

### Kiểm tra status
```bash
kubectl get pods -n hasu-ml | grep spark
```

### Xem logs
```bash
kubectl logs -f -n hasu-ml -l app=spark-master
kubectl logs -f -n hasu-ml -l app=spark-worker
kubectl logs -f -n hasu-ml -l job-name=spark-etl-hybrid
```

### Port-forward Spark UI
```bash
kubectl port-forward -n hasu-ml svc/spark-master 8080:8080
```

## 📚 Tài liệu

- [TROUBLESHOOTING_SPARK.md](./TROUBLESHOOTING_SPARK.md) - Chi tiết các lỗi gặp phải và cách giải quyết
- [05-ml-pipeline/job-spark-etl.yaml](./05-ml-pipeline/job-spark-etl.yaml) - ETL Job cấu hình hiện tại

## 📝 Lý do chuyển namespace

1. **Cross-namespace networking phức tạp**
   - DNS resolution giữa namespaces không hoạt động đúng
   - NetworkPolicy chặn traffic
   - Phải dùng IP tĩnh (pod IP có thể thay đổi)

2. **PVC không thể share**
   - PersistentVolumeClaim là namespace-scoped
   - ETL Job cần access `csv-input-pvc` trong `hasu-ml`

3. **Dễ quản lý hơn**
   - Tất cả ML components trong 1 namespace
   - Chia sẻ secrets, configmaps
   - Đơn giản hóa troubleshooting

## 🔄 Migration Script

Nếu cần recreate Spark cluster, dùng script đã tạo:
```bash
sudo bash /tmp/migrate-spark-to-hasuml.sh
```

## ⚠️ Các file cũ trong k8s/spark/ (outdated)

Các file sau không còn được sử dụng:
- `00-namespace.yaml` - Namespace `spark` đã xóa
- `01-storage.yaml` - PVCs đã tạo trong `hasu-ml`
- `02-spark-master.yaml` - Deployment giờ trong `hasu-ml`
- `03-spark-worker.yaml` - Deployment giờ trong `hasu-ml`
- `04-networkpolicy.yaml` - Không cần vì cùng namespace

---

## 📊 Timeline Migration

```
[2026-03-10 19:15] Bắt đầu - Spark cluster trong namespace 'spark'
[2026-03-10 19:20] ❌ Image "bitnami/spark:latest" không tồn tại
                 → Fix: Đổi sang "apache/spark:3.5.0"

[2026-03-10 19:30] ❌ PVC accessMode ReadWriteMany không support
                 → Fix: Đổi sang ReadWriteOnce, scale worker xuống 1

[2026-03-10 19:40] ❌ Worker node NotReady
                 → Fix: Restart k3s-agent trên worker node

[2026-03-10 19:50] ❌ ResourceQuota thiếu limits cho init containers
                 → Fix: Thêm resources cho tất cả init containers

[2026-03-10 20:00] ❌ Cross-namespace DNS không resolve
                 → Quyết định: Chuyển Spark sang hasu-ml namespace

[2026-03-10 20:30] ❌ Secret thiếu key POSTGRES_USER
                 → Fix: Patch secret hasu-ml-secrets

[2026-03-10 21:00] ✅ Spark cluster chạy trong hasu-ml

[2026-03-10 21:15] ❌ Executor không kết nối được Driver
                 → Fix: Dùng downward API lấy Pod IP làm driver.host

[2026-03-10 21:30] ❌ Cluster deploy mode không hỗ trợ Python
                 → Fix: Dùng client mode thay vì cluster mode

[2026-03-10 21:45] ❌ Resources mismatch (job đòi 2GB, worker chỉ có 1GB)
                 → Fix: Giảm executor memory xuống 512m

[2026-03-10 22:00] ✅ Job hoàn thành thành công!
```

## 🔧 Cấu hình cuối cùng (Working Config)

### Spark Master
```yaml
image: apache/spark:3.5.0
namespace: hasu-ml
resources: 500m-1000m CPU, 1Gi-2Gi memory
```

### Spark Worker
```yaml
image: apache/spark:3.5.0
namespace: hasu-ml
replicas: 1  # Do RWO PVC
env:
  SPARK_WORKER_CORES: "1"
  SPARK_WORKER_MEMORY: "1g"
```

### Spark ETL Job
```yaml
# Key configurations:
spark.driver.bindAddress=0.0.0.0
spark.driver.host=$SPARK_LOCAL_IP  # From downward API
spark.driver.port=4040
spark.executor.memory=512m
spark.executor.cores=1

# Command phải dùng shell để expand env vars:
command: ["/bin/sh", "-c"]
args:
- |
  exec /opt/spark/bin/spark-submit \
    --master "$SPARK_MASTER" \
    --conf "spark.driver.bindAddress=0.0.0.0" \
    --conf "spark.driver.host=$SPARK_LOCAL_IP" \
    --conf "spark.driver.port=4040" \
    --conf "spark.executor.memory=512m" \
    --conf "spark.executor.cores=1" \
    script.py
```

---

**Last Updated:** 2026-03-10  
**Status:** ✅ Spark cluster hoạt động tốt trong hasu-ml namespace  
**Job Status:** ✅ ETL Job chạy thành công (Completed)

---

## 🕐 Timeline Update (2026-03-10 tiếp)

```
[05:00] ❌ DBT Build Job timeout
        → Nguyên nhân: Thiếu volume mounts
        → Fix: Thêm initContainer + volumes

[05:15] ❌ DBT Job lỗi "profiles-dir does not exist"
        → Nguyên nhân: ConfigMaps mount tạo files với "..data" prefix
        → Fix: Dùng initContainer copy files selectively

[05:30] ❌ InvalidImageName ${DOCKERHUB_USERNAME}
        → Nguyên nhân: Biến không được expand khi apply
        → Fix: sed 's|${DOCKERHUB_USERNAME}|annduke|g'

[06:00] ✅ DBT Build Job completed thành công
```

## 📋 Tổng kết tất cả fixes

| File | Thay đổi |
|------|----------|
| `Makefile` | Sửa namespace spark → hasu-ml |
| `job-spark-etl.yaml` | Thêm driver IP, resources |
| `job-dbt-build.yaml` | Thêm initContainer, volumes |
| `cronjob-dbt-daily` | Recreate với đúng volumes |
| `TROUBLESHOOTING_SPARK.md` | Ghi lại 13 lỗi + giải pháp |

## 🔧 Lệnh apply đúng cho DBT Job

```bash
# Cách 1: Dùng sed replace
 cat k8s/05-ml-pipeline/job-dbt-build.yaml | \
   sed 's|${DOCKERHUB_USERNAME}|annduke|g' | \
   kubectl apply -f -

# Cách 2: Export variable rồi dùng envsubst
 export DOCKERHUB_USERNAME=annduke
 envsubst < k8s/05-ml-pipeline/job-dbt-build.yaml | kubectl apply -f -

# Cách 3: Apply trực tiếp stdin (bypass file permission)
 cat << 'YAML' | kubectl apply -f -
 [job content]
 YAML
```


---

## 🕐 Timeline Update (2026-03-10 tiếp theo)

```
[14:00] ❌ Makefile lỗi "job/dbt-build not found"
        → Nguyên nhân: File job-dbt-build.yaml bị ghi đè bằng CronJob
        → Fix: Tạo lại file đúng là Job (không phải CronJob)

[14:30] ⚠️  DBT lỗi "Unknown table expression identifier"
        → Nguyên nhân: Thiếu sync data từ PostgreSQL sang ClickHouse
        → Fix: Chạy make k3s-sync trước, hoặc bỏ qua (không ảnh hưởng)
```

## 📋 Best Practices cho DBT trong K3s

### 1. Tổ chức ConfigMaps
```
dbt-models-staging/         - Staging models
dbt-models-intermediate/    - Intermediate models  
dbt-models-marts-*/         - Marts models (chia nhỏ)
dbt-profiles/               - profiles.yml
dbt-project-files/          - dbt_project.yml
dbt-sources/                - sources.yml
```

### 2. Tách biệt Job và CronJob
| File | Loại | Mục đích |
|------|------|----------|
| job-dbt-build.yaml | Job | Chạy một lần qua Makefile |
| cronjob-dbt-daily.yaml | CronJob | Chạy định kỳ (3 AM) |

### 3. Thứ tự chạy pipeline đúng
```bash
# 1. Sync data
make k3s-sync  # PostgreSQL → ClickHouse

# 2. Build DBT models  
make k3s-dbt   # hoặc trong make app-k3s

# 3. ML Training
make k3s-ml-train
```

## 🔧 Quick Fixes

```bash
# Fix job-dbt-build.yaml bị sai
sudo cp /tmp/job-dbt-build-new.yaml k8s/05-ml-pipeline/job-dbt-build.yaml

# Kiểm tra tất cả ConfigMaps
count_models() {
    kubectl get configmap -n hasu-ml | grep dbt-models | awk '{sum+=$2} END {print "Total: "sum" files"}'
}

# Chạy DBT một lần để test
kubectl apply -f k8s/05-ml-pipeline/job-dbt-build.yaml
kubectl wait --for=condition=complete job/dbt-build -n hasu-ml --timeout=300s
```

