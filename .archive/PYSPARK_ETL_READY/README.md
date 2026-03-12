# PySpark ETL Migration Guide

## 🎯 Tổng quan
Đã viết lại toàn bộ logic từ `data_cleaning/` sang **PySpark**, chạy được trên Spark cluster.

## 📦 Files đã tạo

| File | Mô tả |
|------|-------|
| `etl_full_pyspark.py` | PySpark ETL hoàn chỉnh (products + sales) |
| `Dockerfile.pyspark` | Dockerfile cho PySpark |

## 🔑 Điểm khác biệt: PySpark vs Python Pandas

| Feature | Pandas (cũ) | PySpark (mới) |
|---------|-------------|---------------|
| Engine | Single node | Distributed (cluster) |
| Data size | < 10GB | > 100GB |
| Memory | Load all to RAM | Streaming/chunking |
| Speed | Nhanh với data nhỏ | Scale tốt với data lớn |
| Code | `df.groupby()` | `df.groupBy()` (tương tự) |

## 🚀 Triển khai

### Bước 1: Copy code vào spark-etl/

```bash
# Copy PySpark code
sudo cp PYSPARK_ETL_READY/etl_full_pyspark.py spark-etl/python_etl/

# Copy Dockerfile
sudo cp PYSPARK_ETL_READY/Dockerfile.pyspark spark-etl/Dockerfile
```

### Bước 2: Build Docker Image

```bash
cd spark-etl

# Build
docker build -f Dockerfile -t annduke/hasu-spark-etl:pyspark-v1 .

# Push
docker push annduke/hasu-spark-etl:pyspark-v1
```

### Bước 3: Update K8s Job

Edit `k8s/05-ml-pipeline/job-spark-etl.yaml`:

```yaml
spec:
  template:
    spec:
      containers:
      - name: spark-etl
        image: annduke/hasu-spark-etl:pyspark-v1  # <- Update tag
        command: ["/opt/spark/bin/spark-submit"]
        args:
        - "--master"
        - "spark://spark-master:7077"  # <- Chạy trên cluster
        - "/opt/spark/work-dir/etl_full_pyspark.py"
```

### Bước 4: Deploy

```bash
kubectl delete job spark-etl -n hasu-ml --force
kubectl apply -f k8s/05-ml-pipeline/job-spark-etl.yaml
kubectl logs -n hasu-ml job/spark-etl -f
```

## ✅ Logic đã chuyển đổi

### 1. import_products (data_cleaning → PySpark)

**Pandas (cũ):**
```python
nhom_hang_parsed = df['Nhóm hàng(3 Cấp)'].apply(parse_nhom_hang)
```

**PySpark (mới):**
```python
@udf
def parse_nhom_hang_udf(nhom_hang_str):
    parts = str(nhom_hang_str).split('>>')
    return (parts[0], parts[1], parts[2])

df_parsed = df.withColumn("nhom", parse_nhom_hang_udf(col("nhom_hang")))
```

### 2. import_sales (data_cleaning → PySpark)

**Pandas (cũ):**
```python
trans_agg = trans_df.groupby('ma_giao_dich').agg({'tong_tien': 'sum'})
```

**PySpark (mới):**
```python
trans_agg = trans_df.groupBy("ma_giao_dich").agg(
    spark_sum("tong_tien").alias("tong_tien")
)
```

## 🧪 Testing

```bash
# Kiểm tra Spark cluster đang chạy
kubectl get pods -n hasu-ml | grep spark

# Submit job thủ công
kubectl exec -n hasu-ml deployment/spark-master -- \
  spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode client \
  /opt/spark/work-dir/etl_full_pyspark.py
```

## ⚠️ Lưu ý

1. **Spark cluster phải chạy trước**:
   ```bash
   make spark-deploy
   ```

2. **JDBC drivers** phải có trong `/opt/spark/jars/`:
   - postgresql-42.6.0.jar
   - clickhouse-jdbc-0.6.0-all.jar

3. **Resource allocation**:
   - PySpark cần nhiều memory hơn Pandas
   - Tăng limits trong job config nếu OOM

## 🔄 Rollback

Nếu PySpark không hoạt động, về lại Python:
```bash
# Dùng image cũ
kubectl set image job/spark-etl spark-etl=annduke/hasu-spark-etl:v23
```
