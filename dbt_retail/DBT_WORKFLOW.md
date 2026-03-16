# 🔄 DBT Pipeline Workflow - Tài liệu kỹ thuật

> **Mục đích:** Tài liệu này mô tả chi tiết luồng hoạt động của DBT pipeline, các models và dependencies.  
> **Cập nhật:** 2026-03-16  
> **Phiên bản:** v2.0 (sau PySpark ETL migration)

---

## 📋 Tổng quan Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DBT PIPELINE ARCHITECTURE                            │
└─────────────────────────────────────────────────────────────────────────────┘

Layer 1: SOURCES (ClickHouse Staging Tables)
├── staging_products (15,993 rows)
├── staging_transactions (7,518 rows)  
├── staging_transaction_details (16,293 rows)
├── staging_branches (0 rows - hardcoded)
└── staging_inventory_transactions (2,176 rows)

Layer 2: STAGING MODELS (Views)
├── stg_products
├── stg_transactions
├── stg_transaction_details
├── stg_branches (hardcoded)
└── stg_product_variant_parsing

Layer 3: INTERMEDIATE MODELS (Ephemeral/Views)
├── int_product_performance
├── int_branch_performance
└── int_inventory_movement

Layer 4: MARTS (Tables - ML Source)
├── fct_daily_sales ⭐
├── fct_regular_sales ⭐ (ML main source)
├── fct_monthly_sales
├── fct_promotional_sales
├── fct_inventory_forecast_input
├── dim_product
├── dim_branch
└── rpt_sales_kpi
```

---

## 📊 Schema Chi tiết các Sources

### 1. staging_products (ClickHouse)

| Cột | Kiểu dữ liệu | Mô tả | Ghi chú |
|-----|-------------|-------|---------|
| id | Int64 | ID tự tăng | PK |
| ma_hang | String | Mã sản phẩm | Unique |
| ten_hang | String | Tên sản phẩm | |
| don_vi_tinh | String | Đơn vị tính | |
| cap_1 | String | Nhóm hàng cấp 1 | Từ Excel "Nhóm hàng(3 Cấp)" |
| cap_2 | String | Nhóm hàng cấp 2 | Parse từ chuỗi ">>" |
| cap_3 | String | Nhóm hàng cấp 3 | |
| created_at | DateTime | Thờigian tạo | |
| gia_ban_mac_dinh | Float64 | Giá bán mặc định | ⭐ Thêm từ ETL mới |
| gia_von_mac_dinh | Float64 | Giá vốn mặc định | ⭐ Thêm từ ETL mới |
| quy_doi | Int64 | Tỷ lệ quy đổi | ⭐ Thêm từ ETL mới |

**Lưu ý:** Không có cột `ma_vach`, `thuong_hieu` trong schema hiện tại.

### 2. staging_transactions (ClickHouse)

| Cột | Kiểu dữ liệu | Mô tả | Ghi chú |
|-----|-------------|-------|---------|
| id | Int64 | ID giao dịch | PK |
| ma_giao_dich | String | Mã giao dịch | Từ Excel |
| ngay | String | Ngày (YYYY-MM-DD) | ⭐ Format String |
| ma_chi_nhanh | String | Mã chi nhánh | |
| ten_chi_nhanh | String | Tên chi nhánh | |

**Lưu ý:** Không có cột `chi_nhanh_id`, `thoi_gian`, `doanh_thu`... như schema cũ.

### 3. staging_transaction_details (ClickHouse)

| Cột | Kiểu dữ liệu | Mô tả | Ghi chú |
|-----|-------------|-------|---------|
| id | Int64 | ID chi tiết | PK |
| transaction_id | Int64 | ID giao dịch | FK → staging_transactions.id |
| ma_hang | String | Mã hàng | |
| ten_hang | String | Tên hàng | |
| so_luong | Float64 | Số lượng | |
| don_gia | Float64 | Đơn giá | ⭐ Tên cột khác với schema cũ |
| chiet_khau | Float64 | Chiết khấu | |
| thue_gtgt | Float64 | Thuế GTGT | |
| thanh_tien | Float64 | Thành tiền | |

**Lưu ý:** 
- Không có cột `giao_dich_id`, `gia_ban`, `gia_von`, `loi_nhuan` như schema cũ
- Dùng `transaction_id` (Int64) thay vì `giao_dich_id`
- Dùng `don_gia` thay vì `gia_ban`

---

## 🔄 Data Flow Chi tiết

### 1. Staging Layer

#### stg_products.sql
```sql
Source: staging_products
Transform:
  - id → product_id
  - ma_hang → product_code
  - '' AS barcode (không có trong source)
  - '' AS brand (không có trong source)
  - cap_1/2/3 → category_level_1/2/3
  - gia_von_mac_dinh → default_cost_price
  - gia_ban_mac_dinh → default_selling_price
  - quy_doi (giữ nguyên)
  - Tính default_margin_rate
```

#### stg_transactions.sql
```sql
Source: staging_transactions
Transform:
  - id → transaction_id (String)
  - ma_giao_dich → transaction_code
  - ma_chi_nhanh → branch_id, branch_code
  - ten_chi_nhanh → branch_name
  - toDate(ngay) → transaction_date
  - toDateTime(ngay) → transaction_timestamp
  - 0 AS revenue (không có trong source)
  - 0 AS gross_profit (không có trong source)
```

#### stg_transaction_details.sql
```sql
Source: staging_transaction_details
Join: stg_products (ma_hang = product_code)
Join: stg_transactions (transaction_id = toString(t.transaction_id))
Transform:
  - toString(id) AS detail_id
  - toString(transaction_id) AS transaction_id
  - ma_hang AS product_code
  - so_luong * don_gia AS line_revenue
  - 0 AS line_cost (không có trong source)
```

**⚠️ QUAN TRỌNG:** JOIN giữa stg_transaction_details và stg_transactions cần chú ý type:
- staging_transaction_details.transaction_id là Int64
- stg_transactions.transaction_id là String (đã convert từ id)

### 2. Intermediate Layer

#### int_product_performance.sql
```
Input: stg_transaction_details JOIN stg_transactions
Output: Product metrics
Cột chính:
  - product_code
  - total_revenue (SUM(line_revenue))
  - total_quantity_sold
  - profit_margin
  - abc_class (A/B/C classification)
```

**Lưu ý:** Không có category_l3 trong dữ liệu, cần dùng placeholder ''.

#### int_branch_performance.sql
```
Input: stg_transactions JOIN stg_branches
Output: Branch metrics
Cột chính:
  - branch_code
  - total_transactions
  - total_revenue
  - revenue_rank
```

### 3. Marts Layer

#### fct_regular_sales ⭐ (ML Main Source)
```sql
Input: 
  - staging_transaction_details td
  - staging_transactions t
  - staging_products p
Filter: cap_1 NOT LIKE '%khuyến mại%'
Aggregation:
  - GROUP BY date, product, branch
  - SUM(quantity) AS quantity_sold
  - SUM(thanh_tien) AS gross_revenue
Output: 13,937 rows (158 days)
```

#### fct_daily_sales
```sql
Tương tự fct_regular_sales nhưng không filter promotional
Aggregation daily
```

#### dim_product
```
Input: stg_products JOIN int_product_performance
Output: Product dimension với ABC classification
```

---

## 🔗 Dependencies Graph

```
staging_products ─┬──► stg_products ──┬──► int_product_performance ──┐
                  │                   │                              ├──► dim_product
                  │                   └──► stg_product_variant_parsing│
                  │                                                   │
staging_transactions ──┬──► stg_transactions ───┬──► int_branch_performance ──┤
                       │                        │                             ├──► dim_branch
                       │                        └──► fct_*_sales ◄───────────┤
                       │                                                      │
staging_transaction_details ─► stg_transaction_details ──────────────────────┤
                                                                             │
staging_branches ────────────► stg_branches (hardcoded) ─────────────────────┘
```

---

## ⚠️ Common Issues & Solutions

### Issue 1: Type Mismatch trong JOIN
**Lỗi:** `NO_COMMON_TYPE for types String, Int64`
**Nguyên nhân:** staging_transaction_details.transaction_id (Int64) vs stg_transactions.transaction_id (String)
**Fix:** 
```sql
-- Trong stg_transactions
SELECT toString(id) AS transaction_id ...

-- Hoặc trong JOIN
ON td.transaction_id = toInt64(t.transaction_id)
```

### Issue 2: Missing Columns
**Lỗi:** `Unknown expression identifier 'ma_vach'`
**Nguyên nhân:** Schema staging_products không có cột ma_vach
**Fix:** Dùng placeholder `'' AS barcode`

### Issue 3: Docker Image Outdated
**Lỗi:** Models trong image dùng schema cũ (giao_dich_id, thoi_gian...)
**Fix:** 
- Tạo ConfigMap với models mới
- Mount vào job để override
- Hoặc build image mới

### Issue 4: Seeds Data Error
**Lỗi:** `Cannot parse input: expected ',' before: '.0,0.0,0.0'`
**Nguyên nhân:** File CSV seeds có giá trị không hợp lệ
**Fix:** Xóa seeds không cần thiết hoặc sửa file CSV

---

## 📝 Checklist khi thay đổi DBT

- [ ] Kiểm tra schema ClickHouse thực tế: `DESCRIBE retail_dw.staging_products`
- [ ] Đảm bảo tên cột match với ETL output
- [ ] Kiểm tra kiểu dữ liệu (String vs Int64)
- [ ] Test JOIN giữa các tables
- [ ] Chạy `dbt build` và kiểm tra errors
- [ ] Cập nhật tài liệu này nếu schema thay đổi

---

## 🔧 Commands

```bash
# Chạy DBT build
kubectl delete job dbt-build -n hasu-ml --force
kubectl apply -f k8s/05-ml-pipeline/job-dbt-build.yaml

# Kiểm tra logs
kubectl logs -f job/dbt-build -n hasu-ml

# Kiểm tra schema ClickHouse
kubectl exec clickhouse-5f8f5b445c-6wqxv -n hasu-ml -- clickhouse-client -q "DESCRIBE retail_dw.staging_products"
```

---

## 📚 Related Documents

- `PIPELINE_MAP.md` - Tổng quan toàn bộ pipeline
- `AGENTS.md` - Hướng dẫn cho AI agents
- `../spark-etl/python_etl/etl_main.py` - PySpark ETL logic

---

**Last Updated:** 2026-03-16  
**Maintainer:** Data Engineering Team
