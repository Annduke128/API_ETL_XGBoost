# Quick Reference - Retail Data Pipeline

> Tài liệu tham khảo nhanh cho các thao tác thường dùng

---

## 🚀 Khởi động nhanh

```bash
# 1. Khởi động tất cả
make up

# 2. Kiểm tra health
make health

# 3. Import CSV
make process

# 4. Chạy DBT
make dbt

# 5. Train ML
make ml
```

---

## 📊 Kiểm tra dữ liệu

### PostgreSQL
```bash
make psql

# Hoặc query trực tiếp
docker-compose exec -T postgres psql -U retail_user -d retail_db -c "
  SELECT 
    'Products' as item, COUNT(*) as count FROM products
  UNION ALL
  SELECT 'Transactions', COUNT(*) FROM transactions;
"
```

### ClickHouse
```bash
make clickhouse

# Query
docker-compose exec -T clickhouse clickhouse-client -q "
  SELECT COUNT(*) FROM retail_dw.fact_transactions
"
```

---

## 📁 Import CSV

### Cách 1: Copy file và chạy
```bash
cp /path/to/file.csv csv_input/
make process
```

### Cách 2: Auto-watch mode
```bash
make csv-watch
# Từ giờ mỗi file copy vào sẽ tự xử lý
```

---

## 🔧 DBT Commands

| Lệnh | Mô tả |
|------|-------|
| `make dbt` | Run tất cả models |
| `make dbt-seed` | Load seeds |
| `make dbt-test` | Run tests |
| `make dbt-docs` | Generate docs |

### Chạy specific models
```bash
docker-compose run --rm -e POSTGRES_HOST=postgres dbt run --select staging
docker-compose run --rm -e POSTGRES_HOST=postgres dbt run --select marts.sales
docker-compose run --rm -e POSTGRES_HOST=postgres dbt run --select stg_seed_products
```

---

## 🤖 ML Commands

| Lệnh | Mô tả |
|------|-------|
| `make ml` | Train all models |
| `make ml-train` | Train forecasting |
| `make ml-predict` | Generate predictions |

---

## 🔍 Troubleshooting

### Xem logs
```bash
make logs                    # Tất cả
docker-compose logs postgres # Specific service
```

### Restart service
```bash
docker-compose restart clickhouse
docker-compose restart superset-web
```

### Reset cache
```bash
docker-compose exec redis redis-cli FLUSHDB
```

### Full reset (⚠️ mất dữ liệu)
```bash
make reset-all
make up
```

---

## 🌐 Truy cập UI

| Service | URL | Login |
|---------|-----|-------|
| **Superset** | http://localhost:8088 | admin/admin |
| **Airflow** | http://localhost:8085 | admin/admin |
| **DBT Docs** | http://localhost:8080 | - |

---

## 📝 SQL mẫu

### Top sản phẩm bán chạy
```sql
SELECT 
  p.ten_hang,
  SUM(td.so_luong) as total_qty,
  SUM(td.tong_loi_nhuan) as total_profit
FROM transaction_details td
JOIN products p ON td.product_id = p.id
GROUP BY p.ten_hang
ORDER BY total_qty DESC
LIMIT 10;
```

### Doanh thu theo ngày
```sql
SELECT 
  DATE(thoi_gian) as ngay,
  SUM(doanh_thu) as doanh_thu,
  SUM(loi_nhuan_gop) as loi_nhuan
FROM transactions
GROUP BY DATE(thoi_gian)
ORDER BY ngay DESC;
```

### ClickHouse - Tổng hợp nhanh
```sql
SELECT 
  chi_nhanh,
  COUNT(*) as so_giao_dich,
  SUM(doanh_thu) as tong_doanh_thu,
  AVG(profit_margin) as avg_margin
FROM retail_dw.fact_transactions
GROUP BY chi_nhanh
ORDER BY tong_doanh_thu DESC;
```

---

## ⚡ One-liners

```bash
# Check all in one
make status && make health && echo "✅ All good!"

# Quick CSV + DBT
make csv-reset && cp your_file.csv csv_input/ && make process && make dbt

# Full pipeline reset and run
make reset-all && make up && sleep 60 && make process && make dbt && make ml

# Backup data
docker-compose exec postgres pg_dump -U retail_user retail_db > backup.sql

# Restore data
docker-compose exec -T postgres psql -U retail_user -d retail_db < backup.sql
```

---

## 📞 Cần help?

```bash
make help        # Xem tất cả commands
```
