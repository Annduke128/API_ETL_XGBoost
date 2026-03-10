# 🚨 Troubleshooting Guide: Spark on K3s

> Tài liệu tổng hợp các vấn đề gặp phải khi triển khai Spark trên K3s và cách giải quyết.
> 
> **Ngày cập nhật:** 2026-03-05  
> **Tác giả:** Kimi AI Assistant  
> **Dự án:** Hasu ML Pipeline

---

## 📋 Mục lục

1. [Tổng quan lỗi](#1-tổng-quan-lỗi)
2. [Danh sách lỗi và giải pháp](#2-danh-sách-lỗi-và-giải-pháp)
3. [Best Practices](#3-best-practices)
4. [Câu lệnh hữu ích](#4-câu-lệnh-hữu-ích)

---

## 1. Tổng quan lỗi

```
┌─────────────────────────────────────────────────────────────────────┐
│                    KẾT QUẢ CUỐI CÙNG                               │
├─────────────────────────────────────────────────────────────────────┤
│  ✅ Spark Cluster: Hoạt động (1 Master + 1 Worker)                 │
│  ✅ Spark ETL Job: Chạy thành công trong namespace hasu-ml         │
│  ✅ Cross-namespace: Giải quyết bằng cách chuyển sang 1 namespace  │
└─────────────────────────────────────────────────────────────────────┘
```

### Timeline các vấn đề gặp phải:

```
[19:15] ❌ Image "bitnami/spark:latest" không tồn tại
[19:25] ❌ PVC accessMode ReadWriteMany không support với local-storage
[19:30] ❌ Worker node "k3s-worker-gpu" NotReady
[19:45] ❌ ResourceQuota thiếu limits cho init containers
[20:00] ❌ Job cần PVC từ hasu-ml nhưng chạy trong namespace spark
[20:15] ❌ Custom image thiếu Java
[20:30] ❌ Secret thiếu key POSTGRES_USER
[20:45] ❌ Cross-namespace DNS không resolve (spark-master.spark)
[21:00] ✅ Giải pháp: Chuyển toàn bộ Spark sang hasu-ml
```

---

## 2. Danh sách lỗi và giải pháp

### ❌ Lỗi 1: Image "bitnami/spark:latest" không tồn tại

**Triệu chứng:**
```
Failed to pull image "bitnami/spark:latest": 
rpc error: code = NotFound desc = failed to pull and unpack image "docker.io/bitnami/spark:latest"
```

**Nguyên nhân:**
- Tag `latest` không tồn tại trên Docker Hub cho repo `bitnami/spark`
- Bitnami đã thay đổi cách tag images

**Giải pháp:**
```yaml
# ❌ Sai
image: bitnami/spark:latest

# ✅ Đúng
image: apache/spark:3.5.0
```

**Best Practice:**
- Luôn dùng **semantic version** (e.g., `3.5.0`) thay vì `latest`
- Kiểm tra image trước khi deploy: `docker pull apache/spark:3.5.0`

---

### ❌ Lỗi 2: PVC accessMode ReadWriteMany không support

**Triệu chứng:**
```
Warning  FailedBinding  3m  persistentvolume-controller  
no persistent volumes available for this claim and no storage class is set
```

**Nguyên nhân:**
- StorageClass `local-storage` (local-path provisioner) chỉ hỗ trợ `ReadWriteOnce` (RWO)
- Không thể mount cùng PVC vào nhiều pods khác nhau với `ReadWriteMany` (RWX)

**Giải pháp:**
```yaml
# ❌ Sai
spec:
  accessModes:
    - ReadWriteMany  # Không support với local-storage

# ✅ Đúng
spec:
  accessModes:
    - ReadWriteOnce  # Chỉ 1 pod mount tại 1 thờ i điểm
```

**Best Practice:**
- Local-path provisioner chỉ hỗ trợ RWO
- Nếu cần RWX, phải dùng: NFS, Longhorn, Rook-Ceph, hoặc hostPath
- Scale worker xuống 1 replica nếu dùng RWO

---

### ❌ Lỗi 3: Worker node NotReady

**Triệu chứng:**
```
kubectl get nodes
NAME               STATUS     ROLES                  AGE
k3s-master         Ready      control-plane,master   3d
k3s-worker-gpu     NotReady   <none>                 3d  ← ❌
```

**Nguyên nhân:**
- K3s agent trên worker node bị dừng hoặc crash
- Network issues giữa master và worker

**Giải pháp:**
```bash
# SSH vào worker node
ssh k3s-worker-gpu

# Restart k3s-agent
sudo systemctl restart k3s-agent

# Kiểm tra logs
sudo journalctl -u k3s-agent -f
```

**Prevention:**
```bash
# Thêm vào crontab để auto-restart
@reboot sudo systemctl start k3s-agent

# Hoặc dùng systemd timer
sudo systemctl enable k3s-agent
```

---

### ❌ Lỗi 4: ResourceQuota thiếu limits cho init containers

**Triệu chứng:**
```
Error creating: pods "spark-etl-xxx" is forbidden: 
failed quota: hasu-ml-quota: 
must specify limits.cpu,limits.memory
```

**Nguyên nhân:**
- ResourceQuota yêu cầu **tất cả containers** phải có limits
- Init containers cũng phải có limits, không chỉ main container

**Giải pháp:**
```yaml
# ❌ Sai - Thiếu resources cho init container
initContainers:
- name: wait-for-spark
  image: busybox:1.36
  # Thiếu resources!

# ✅ Đúng - Có resources cho cả init và main
initContainers:
- name: wait-for-spark
  image: busybox:1.36
  resources:
    limits:
      cpu: "100m"
      memory: "64Mi"
    requests:
      cpu: "50m"
      memory: "32Mi"
```

**Best Practice:**
- Luôn đặt resources cho **mọi container** (init và main)
- Init containers thường nhẹ: `100m/64Mi` là đủ

---

### ❌ Lỗi 5: Job cần PVC từ namespace khác

**Triệu chứng:**
```
Warning  FailedMount  10s  kubelet  
Unable to attach or mount volumes: unmounted volumes=[csv-input]
```

**Nguyên nhân:**
- PVC là **namespace-scoped** - không thể dùng chung giữa namespaces
- Job chạy trong `spark` namespace nhưng PVC ở `hasu-ml`

**Giải pháp 1 (Chuyển Job sang namespace có PVC):**
```yaml
metadata:
  namespace: hasu-ml  # Chuyển sang namespace có PVC
```

**Giải pháp 2 (Tạo PVC mới trong namespace Job):**
```yaml
# Tạo PVC trùng tên trong mỗi namespace
# Nhưng dữ liệu sẽ KHÁC NHAU (không share được)
```

**Best Practice:**
- PVCs không thể share cross-namespace
- Nên đặt tất cả workloads cần cùng dữ liệu trong **cùng 1 namespace**
- Hoặc dùng NFS/shared storage nếu cần share thực sự

---

### ❌ Lỗi 6: Custom image thiếu Java

**Triệu chứng:**
```
/opt/entrypoint.sh: exec: line 35: java: not found
```

**Nguyên nhân:**
- Custom image `hasu-spark-etl` build sai - không có Java trong PATH
- Dockerfile thiếu `ENV JAVA_HOME` hoặc sai `PATH`

**Giải pháp:**
```yaml
# ❌ Sai - Dùng custom image thiếu Java
image: hasu-spark-etl:latest

# ✅ Đúng - Dùng official image
image: apache/spark:3.5.0
```

**Nếu vẫn muốn custom image:**
```dockerfile
FROM apache/spark:3.5.0
# Kế thừa Java từ base image
COPY spark_etl.py /app/
```

---

### ❌ Lỗi 7: Secret thiếu key

**Triệu chứng:**
```
Error: secret "hasu-ml-secrets" not found key "POSTGRES_USER"
```

**Nguyên nhân:**
- Secret tạo từ env var thiếu key
- `POSTGRES_USER` không được export hoặc là empty

**Giải pháp:**
```bash
# Kiểm tra secret
kubectl get secret hasu-ml-secrets -n hasu-ml -o yaml

# Patch thêm key
kubectl patch secret hasu-ml-secrets -n hasu-ml --type merge -p '
{
  "stringData": {
    "POSTGRES_USER": "retail_user"
  }
}'

# Hoặc recreate secret
kubectl create secret generic hasu-ml-secrets \
  --from-literal=POSTGRES_USER=retail_user \
  --from-literal=POSTGRES_PASSWORD=xxx \
  -n hasu-ml --dry-run=client -o yaml | kubectl apply -f -
```

**Best Practice:**
- Luôn verify secret trước khi deploy
- Dùng `--dry-run=client -o yaml` để preview

---

### ❌ Lỗi 8: Cross-namespace DNS không resolve

**Triệu chứng:**
```
# Từ pod trong namespace hasu-ml
$ nslookup spark-master.spark
Server: 10.43.0.10
Address: 10.43.0.10:53

** server can't find spark-master.spark: NXDOMAIN
```

**Nguyên nhân:**
1. DNS format: `service-name.namespace.svc.cluster.local`
2. NetworkPolicy `default-deny-all` chặn traffic cross-namespace
3. Coredns có thể không resolve đúng

**Giải pháp 1: Dùng IP (Workaround):**
```yaml
env:
- name: SPARK_MASTER
  value: "spark://10.43.1.246:7077"  # IP của spark-master service
```
**⚠️ Lưu ý:** Pod IP có thể thay đổi khi restart!

**Giải pháp 2: Dùng FQDN (Nếu network cho phép):**
```yaml
env:
- name: SPARK_MASTER
  value: "spark://spark-master.spark.svc.cluster.local:7077"
```

**Giải pháp 3: Chuyển sang cùng namespace (Khuyến nghị):**
```yaml
# Spark Master và ETL Job đều trong hasu-ml
metadata:
  namespace: hasu-ml

# Khi đó chỉ cần
value: "spark://spark-master:7077"
```

**Best Practice:**
- Nếu workloads cần giao tiếp nhiều → **cùng 1 namespace**
- Nếu phải tách namespace → thêm NetworkPolicy allow cross-namespace

---

## 3. Best Practices

### 🏗️ Kiến trúc khuyến nghị

```
┌─────────────────────────────────────────────────────────────┐
│                    Namespace: hasu-ml                        │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   PostgreSQL │    │  Spark       │    │  ClickHouse  │  │
│  │   (Primary)  │◄──►│  Master      │◄──►│   (OLAP)     │  │
│  └──────────────┘    └──────┬───────┘    └──────────────┘  │
│                             │                               │
│                        ┌────┴────┐                         │
│                        │ Worker  │                         │
│                        └────┬────┘                         │
│                             │                               │
│  ┌──────────────────────────▼──────────────────────────┐   │
│  │              Spark ETL Job (Hybrid)                  │   │
│  │         Read CSV → PostgreSQL → ClickHouse          │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 📋 Checklist trước khi deploy

```markdown
- [ ] Image tồn tại và có tag cụ thể (không dùng `latest`)
- [ ] PVC accessMode tương thích với StorageClass
- [ ] Tất cả containers (init + main) đều có resource limits
- [ ] Secrets đã tạo đầy đủ các key cần thiết
- [ ] Các workloads cần giao tiếp trong cùng namespace
- [ ] Worker nodes đều Ready
- [ ] NetworkPolicy không chặn traffic cần thiết
```

### 🔧 Resource Limits khuyến nghị

| Component | CPU Request | CPU Limit | Memory Request | Memory Limit |
|-----------|-------------|-----------|----------------|--------------|
| Spark Master | 500m | 1000m | 1Gi | 2Gi |
| Spark Worker | 500m | 1000m | 1Gi | 2Gi |
| Init Containers | 50m | 100m | 32Mi | 64Mi |
| ETL Job | 2000m | 4000m | 4Gi | 8Gi |

---

## 4. Câu lệnh hữu ích

### Debug Pod
```bash
# Xem logs
kubectl logs -f <pod-name> -n <namespace>

# Xem events
kubectl get events -n <namespace> --sort-by='.lastTimestamp'

# Exec vào pod
kubectl exec -it <pod-name> -n <namespace> -- /bin/sh

# Describe pod (xem chi tiết lỗi)
kubectl describe pod <pod-name> -n <namespace>
```

### Debug Network
```bash
# Test DNS từ trong pod
kubectl run -it --rm debug --image=busybox:1.36 --restart=Never -- nslookup spark-master

# Test connectivity
kubectl run -it --rm debug --image=busybox:1.36 --restart=Never -- nc -zv spark-master 7077

# Xem service endpoints
kubectl get endpoints spark-master -n <namespace>
```

### Debug Storage
```bash
# Xem PVC status
kubectl get pvc -n <namespace>

# Xem PV
kubectl get pv

# Xem StorageClass
kubectl get storageclass

# Describe PVC
kubectl describe pvc <pvc-name> -n <namespace>
```

### Cleanup
```bash
# Xóa job cũ
kubectl delete job spark-etl-hybrid -n hasu-ml --ignore-not-found

# Xóa pods completed/evicted
kubectl get pods --all-namespaces --field-selector=status.phase=Failed
kubectl delete pods --all-namespaces --field-selector=status.phase=Failed

# Xóa namespace (⚠️ Mất dữ liệu)
kubectl delete namespace spark
```

---

## 📚 Tài liệu tham khảo

- [Apache Spark on K8s](https://spark.apache.org/docs/latest/running-on-kubernetes.html)
- [K3s Storage](https://docs.k3s.io/storage)
- [Kubernetes Resource Quotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/)
- [DNS for Services](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)

---

## 📝 Changelog

| Ngày | Mô tả | Người cập nhật |
|------|-------|----------------|
| 2026-03-05 | Tạo tài liệu | Kimi AI |
| | | |

---

**Lưu ý:** Tài liệu này cần được cập nhật khi có thay đổi về infrastructure hoặc gặp thêm vấn đề mới.

### ❌ Lỗi 9: Executor không kết nối được Driver

**Triệu chứng:**
```
WARN TaskSchedulerImpl: Initial job has not accepted any resources
Executor updated: app-xxx/0 is now EXITED (Command exited with code 1)
```

**Nguyên nhân:**
- Driver (trong Job pod) bind vào hostname mà executor (trong Worker pod) không resolve được
- Mặc định Spark dùng hostname của pod làm driver host, nhưng worker không thể DNS resolve

**Giải pháp:**
```yaml
# Sử dụng downward API để lấy Pod IP
env:
- name: SPARK_LOCAL_IP
  valueFrom:
    fieldRef:
      fieldPath: status.podIP

# Trong command, cấu hình driver đúng
command: ["/bin/sh", "-c"]
args:
- |
  exec /opt/spark/bin/spark-submit \
    --master "$SPARK_MASTER" \
    --conf "spark.driver.bindAddress=0.0.0.0" \
    --conf "spark.driver.host=$SPARK_LOCAL_IP" \
    --conf "spark.driver.port=4040" \
    /path/to/script.py
```

**Best Practice:**
- Luôn set `spark.driver.host` bằng Pod IP khi chạy trong Kubernetes
- Dùng `spark.driver.bindAddress=0.0.0.0` để accept kết nối từ mọi interface

---

### ❌ Lỗi 10: Cluster deploy mode không hỗ trợ Python

**Triệu chứng:**
```
org.apache.spark.SparkException: Cluster deploy mode is currently not supported for python applications on standalone clusters.
```

**Nguyên nhân:**
- Spark standalone cluster KHÔNG hỗ trợ cluster mode cho Python applications
- Chỉ hỗ trợ client mode cho Python

**Giải pháp:**
```bash
# ❌ Sai - Cluster mode không hỗ trợ Python
spark-submit --deploy-mode cluster --master spark://spark-master:7077 app.py

# ✅ Đúng - Client mode cho Python
spark-submit --master spark://spark-master:7077 app.py
```

---

### ❌ Lỗi 11: Resources mismatch giữa Job và Worker

**Triệu chứng:**
```
WARN Master: App app-xxx requires more resource than any of Workers could have.
```

**Nguyên nhân:**
- Job yêu cầu executor memory nhiều hơn worker có thể cung cấp
- Ví dụ: Job đòi `spark.executor.memory=2g` nhưng worker chỉ có `1GB`

**Giải pháp:**
```bash
# Giảm executor memory để phù hợp với worker
spark-submit \
  --conf "spark.executor.memory=512m" \
  --conf "spark.executor.cores=1" \
  app.py
```

**Hoặc tăng resources cho Worker:**
```yaml
# Trong Deployment của Worker
env:
- name: SPARK_WORKER_MEMORY
  value: "2g"
- name: SPARK_WORKER_CORES
  value: "2"
```

**Best Practice:**
- Executor memory nên ≤ 80% Worker memory
- Luôn kiểm tra worker resources trước khi submit job

---

## 📝 Changelog

| Ngày | Mô tả | Ngườ i cập nhật |
|------|-------|----------------|
| 2026-03-05 | Tạo tài liệu | Kimi AI |
| 2026-03-10 | Thêm lỗi 9, 10, 11 - Executor connection, Cluster mode Python, Resources mismatch | Kimi AI |
