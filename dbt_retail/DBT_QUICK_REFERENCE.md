# 📘 DBT Quick Reference Guide

> Hướng dẫn nhanh cho developers làm việc với DBT pipeline

---

## 🎯 Schema Mapping (Quan trọng)

### Từ PostgreSQL → ClickHouse → DBT

| Excel Column | PostgreSQL | ClickHouse | DBT Model |
|-------------|------------|------------|-----------|
| Mã hàng | ma_hang | ma_hang | product_code |
| Tên hàng | ten_hang | ten_hang | product_name |
| Giá bán | gia_ban_mac_dinh | gia_ban_mac_dinh | default_selling_price |
| Giá vốn | gia_von_mac_dinh | gia_von_mac_dinh | default_cost_price |
| Quy đổi | quy_doi | quy_doi | quy_doi |
| Nhóm hàng(3 Cấp) | cap_1/2/3 | cap_1/2/3 | category_level_1/2/3 |
| Mã giao dịch | ma_giao_dich | ma_giao_dich | transaction_code |
| Thờigian | ngay | ngay (String) | transaction_date |
| Chi nhánh | ma_chi_nhanh | ma_chi_nhanh | branch_code |

---

## ⚠️ Những điều KHÔNG được thay đổi

### 1. Tên cột trong sources.yml
```yaml
# ĐÚNG
tables:
  - name: staging_products
    columns: [ma_hang, ten_hang, gia_ban_mac_dinh, quy_doi, ...]
  
  - name: staging_transactions
    columns: [id, ma_giao_dich, ngay, ma_chi_nhanh, ...]
```

### 2. JOIN conditions
```sql
-- ĐÚNG
ON td.transaction_id = t.id
ON p.ma_hang = td.ma_hang
ON t.ma_chi_nhanh = b.branch_code
```

### 3. Các cột hardcoded trong stg_transactions
```sql
-- KHÔNG xóa các cột này
toFloat64(0) AS revenue,
toFloat64(0) AS gross_profit
```

---

## 🔧 Sửa lỗi thường gặp

### Lỗi: `Unknown identifier 'giao_dich_id'`
**Sửa:** Dùng `transaction_id` thay vì `giao_dich_id`

### Lỗi: `Unknown identifier 'thoi_gian'`
**Sửa:** Dùng `ngay` và `toDate(ngay)`

### Lỗi: `NO_COMMON_TYPE String/Int64`
**Sửa:** 
```sql
ON toString(s.transaction_id) = t.transaction_id
-- hoặc
ON s.transaction_id = toInt64(t.transaction_id)
```

### Lỗi: `Unknown identifier 'ma_vach'`
**Sửa:** Dùng `'' AS barcode`

---

## 🚀 Testing sau khi sửa

```bash
# 1. Cập nhật ConfigMap
kubectl create configmap dbt-code \
  --from-file=stg_products.sql=models/staging/stg_products.sql \
  -n hasu-ml --dry-run=client -o yaml | kubectl apply -f -

# 2. Chạy DBT build
kubectl delete job dbt-build -n hasu-ml --force
kubectl apply -f k8s/05-ml-pipeline/job-dbt-build.yaml

# 3. Kiểm tra kết quả
kubectl logs -f job/dbt-build -n hasu-ml
```

---

## 📞 Cần help?

1. Đọc `DBT_WORKFLOW.md` đầy đủ
2. Kiểm tra schema ClickHouse: `DESCRIBE retail_dw.staging_products`
3. So sánh với ETL output trong `spark-etl/python_etl/etl_main.py`

---

**Ghi nhớ:** Luôn kiểm tra schema thực tế trong ClickHouse trước khi thay đổi DBT models!
