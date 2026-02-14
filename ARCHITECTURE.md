# Kiến trúc Database - Phân tích 3 hệ thống lưu trữ

## Tổng quan

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA FLOW ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   CSV Input ──▶ PostgreSQL (OLTP) ──▶ ClickHouse (DW) ──▶ BI/Analytics    │
│                                             │                               │
│                                             ▼                               │
│                                       Fact Tables                           │
│                                       Aggregations                          │
│                                       Time-series                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. PostgreSQL - OLTP Database

### 🎯 Mục đích
**Online Transaction Processing** - Xử lý giao dịch thờigian thực, lưu trữ dữ liệu chuẩn hóa.

### 📦 Dữ liệu lưu trữ

```
PostgreSQL Schema (retail_db)
│
├── branches              # Chi nhánh (normalized)
│   ├── id, ma_chi_nhanh, ten_chi_nhanh, dia_chi, thanh_pho
│
├── products              # Sản phẩm (normalized)  
│   ├── id, ma_hang, ten_hang, thuong_hieu, nhom_hang_cap_1/2/3
│   ├── gia_von_mac_dinh, gia_ban_mac_dinh
│
├── transactions          # Giao dịch header
│   ├── id, ma_giao_dich, chi_nhanh_id, thoi_gian
│   ├── tong_tien_hang, giam_gia, doanh_thu, tong_gia_von, loi_nhuan_gop
│
├── transaction_details   # Chi tiết giao dịch (line items)
│   ├── id, giao_dich_id, product_id, so_luong
│   ├── gia_ban, gia_von, loi_nhuan, tong_loi_nhuan
│
└── ml_forecasts          # Kết quả dự báo ML
    ├── forecast_date, ma_hang, predicted_quantity, predicted_revenue
```

### ✨ Tại sao chọn PostgreSQL?

| Yếu tố | Lý do |
|--------|-------|
| **ACID Compliance** | Đảm bảo tính nhất quán cho giao dịch tài chính |
| **Relational Model** | Chuẩn hóa dữ liệu, giảm redundancy, dễ maintain |
| **JSON Support** | Linh hoạt với semi-structured data nếu cần |
| **Extensions** | PostGIS (nếu cần location), TimescaleDB (time-series) |
| **Open Source** | Miễn phí, community lớn, tài liệu phong phú |
| **Concurrency** | Xử lý nhiều giao dịch đồng thờigian tốt |

### 💼 Use Cases

1. **POS System Integration** - Lưu giao dịch bán hàng real-time
2. **Inventory Management** - Quản lý tồn kho, nhập/xuất
3. **Master Data** - Sản phẩm, chi nhánh, khách hàng
4. **Transactional Reports** - Báo cáo giao dịch chi tiết

### 📊 Performance

- **Write-heavy**: Tối ưu cho INSERT/UPDATE liên tục
- **Row-oriented**: Phù hợp đọc từng record
- **Index**: B-tree indexes trên ma_giao_dich, thoi_gian

---

## 2. ClickHouse - Data Warehouse

### 🎯 Mục đích  
**OLAP (Online Analytical Processing)** - Phân tích dữ liệu lớn, truy vấn nhanh, lưu trữ time-series.

### 📦 Dữ liệu lưu trữ

```
ClickHouse Schema (retail_dw)
│
├── fact_transactions           # Fact table chính
│   ├── thoi_gian (DateTime), ngay (Date)
│   ├── ma_giao_dich, chi_nhanh, ma_hang
│   ├── ten_hang, thuong_hieu, nhom_hang_cap_1/2/3
│   ├── cap_1, cap_2, cap_3 (phân loại)
│   ├── so_luong, gia_ban, gia_von, loi_nhuan
│   ├── doanh_thu, giam_gia, tong_gia_von, loi_nhuan_gop
│   └── ty_suat_loi_nhuan, etl_timestamp
│   
├── agg_daily_sales             # Aggregated (Materialized View)
│   ├── ngay, chi_nhanh, nhom_hang_cap_1/2
│   ├── tong_doanh_thu (AggregateFunction)
│   ├── tong_loi_nhuan (AggregateFunction)
│   └── so_giao_dich (AggregateFunction)
│
└── mv_daily_sales              # Auto-aggregate view
```

### ✨ Tại sao chọn ClickHouse?

| Yếu tố | Lý do |
|--------|-------|
| **Column-oriented** | Nén tốt, đọc nhanh khi query few columns |
| **Vectorized Execution** | Xử lý hàng triệu rows/giây |
| **Partitioning** | PARTITION BY toYYYYMM() - query theo tháng nhanh |
| **MergeTree Engine** | Tự động merge parts, optimize storage |
| **Materialized Views** | Pre-aggregate data tự động |
| **Time-series** | Rất tốt cho dữ liệu theo thờigian |

### 💼 Use Cases

1. **BI Dashboards** - Truy vấn nhanh cho Superset/Tableau
2. **Time-series Analytics** - Xu hướng bán hàng theo thờigian
3. **Aggregated Reports** - Báo cáo tổng hợp (SUM, AVG, COUNT)
4. **Large Dataset Scans** - Phân tích toàn bộ lịch sử

### 📊 Performance

```sql
-- ClickHouse query ví dụ - Chạy rất nhanh
docker-compose exec -T clickhouse clickhouse-client -q "
SELECT 
  chi_nhanh,
  SUM(doanh_thu) as revenue,
  AVG(profit_margin) as avg_margin
FROM retail_dw.fact_transactions
WHERE ngay >= today() - 30
GROUP BY chi_nhanh
ORDER BY revenue DESC
"
```

- **Read-heavy**: Tối ưu SELECT, aggregates
- **Compression**: 10x smaller than PostgreSQL
- **Parallel Processing**: Tự động parallel trên nhiều cores

---

## 🔍 So sánh chi tiết

### Feature Comparison

| Feature | PostgreSQL | ClickHouse |
|---------|------------|------------|
| **Storage Model** | Row-oriented | Column-oriented |
| **Primary Use** | OLTP | OLAP |
| **Best For** | Transactions | Analytics |
| **Write Speed** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Read Speed (Aggregates)** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Compression** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Scalability** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Maintenance** | Low | Very Low |
| **License** | Open Source | Open Source |

### Query Performance Example

**Scenario**: Tính tổng doanh thu 30 ngày qua group by chi nhánh

```sql
-- PostgreSQL: ~5-10 giây (với 10M rows)
-- ClickHouse: ~0.5-1 giây (với 10M rows)
```

---

## 🔄 Data Flow chi tiết

### 1. Ingestion Flow

```
CSV File
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  Data Cleaning (Python)                                       │
│  - Remove duplicates                                          │
│  - Normalize encoding                                         │
│  - Validate data types                                        │
└──────────────────────────────────────────────────────────────┘
    │
    ├──────────────────┬──────────────────┐
    ▼                  ▼                  ▼
PostgreSQL      ClickHouse         Redis
   │                 │               (Cache)
   │                 │                  │
   ▼                 ▼                  ▼
OLTP Storage    DW Storage       Temp Buffer
(Normalized)    (Denormalized)
```

### 2. ETL Flow (DBT)

```
PostgreSQL (Sources)
    │
    ▼
┌────────────────────────────────────────────┐
│  DBT Staging Models                         │
│  - Clean column names                       │
│  - Type casting                             │
│  - Basic calculations                       │
└────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────┐
│  DBT Intermediate Models                    │
│  - Business logic                           │
│  - Aggregations                             │
│  - ABC Classification                       │
│  - RFM Analysis                             │
└────────────────────────────────────────────┘
    │
    ├──────────────┐
    ▼              ▼
PostgreSQL    ClickHouse
(Marts)        (Marts)
```

### 3. Query Routing

| Use Case | Database | Lý do |
|----------|----------|-------|
| Tra cứu giao dịch theo mã | PostgreSQL | Index trên ma_giao_dich, tìm nhanh |
| Báo cáo doanh thu tháng | ClickHouse | Aggregate nhanh, partition by month |
| Real-time inventory | PostgreSQL | Consistency, ACID |
| ML Training data | ClickHouse | Scan nhiều data nhanh |

---

## 🎯 Khi nào dùng database nào?

### Chọn PostgreSQL khi:
- ✅ Cần lưu giao dịch real-time
- ✅ Data cần chuẩn hóa, ít redundancy
- ✅ Có nhiều UPDATE/DELETE
- ✅ Cần ACID compliance (ngân hàng, kế toán)
- ✅ Team quen SQL chuẩn

### Chọn ClickHouse khi:
- ✅ Phân tích dữ liệu lớn (TBs)
- ✅ Query aggregate (SUM, AVG, COUNT)
- ✅ Time-series data (logs, metrics)
- ✅ Read-heavy, ít UPDATE
- ✅ Cần tốc độ scan nhanh

---

## 📈 Capacity Planning

### PostgreSQL
- **Dung lượng**: 100GB - 1TB
- **Rows**: 10M - 100M giao dịch
- **Backup**: Daily pg_dump
- **Scale**: Read replicas nếu cần

### ClickHouse
- **Dung lượng**: 1TB - 10TB (nén)
- **Rows**: 1B+ events
- **Backup**: Freeze partitions
- **Scale**: Sharding clusters

---

## 🔐 Bảo mật

### PostgreSQL
```sql
-- User roles
CREATE USER app_read ONLY;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_read;
```

### ClickHouse
```sql
-- Row policy
CREATE ROW POLICY policy1 ON fact_transactions 
FOR SELECT USING chi_nhanh = currentUser() TO USER analyst;
```

---

**Kết luận**: Kiến trúc 2-tier này cho phép:
- **PostgreSQL**: Xử lý giao dịch nhanh, reliable (OLTP)
- **ClickHouse**: Phân tích dữ liệu lớn real-time (OLAP)

Mỗi database làm tốt nhất nhiệm vụ của nó, không có database nào "tốt nhất cho tất cả".
