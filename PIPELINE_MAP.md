# 🗺️ VISUAL PIPELINE MAP - TỔNG QUAN HỆ THỐNG

> Tài liệu này mô tả toàn bộ pipeline dữ liệu từ nguồn đến ML models  
> **Cập nhật:** 2026-03-16  
> **Trạng thái:** ✅ Đã fix giá sản phẩm, Inventory import trực tiếp CH, Thêm cột quy đổi, PO logic hoàn thiện

---

## 📊 Tổng quan các thành phần

| Layer | Thành phần | Số lượng | Mô tả |
|-------|-----------|----------|-------|
| 1 | CSV Source Files | **3** | DanhSachSanPham.csv + BaoCaoBanHang.xlsx + **BaoCaoXuatNhapTon.xlsx** |
| 2 | PySpark ETL | 1 | etl_main.py - Import products→PG, inventory→CH |
| 3 | PostgreSQL Tables | **5** | Database chính lưu dữ liệu gốc |
| 4 | ClickHouse Staging | **4** | Raw data từ PostgreSQL |
| 5 | DBT Staging Models | 4 | Views xử lý cơ bản |
| 6 | DBT Intermediate | 3 | Models trung gian |
| 7 | DBT Dimensions | 3 | Dimension tables |
| 8 | DBT Facts | **6** | Fact tables cho ML & báo cáo |
| 9 | ML Pipeline | 1 | XGBoost forecasting |

---

## 📋 CHI TIẾT COLUMN MAPPING

### Layer 1: CSV Sources

#### 📄 DanhSachSanPham.csv → PostgreSQL.products

| CSV Column | PostgreSQL Column | Data Type | Description |
|------------|-------------------|-----------|-------------|
| `Mã hàng` | `ma_hang` | VARCHAR(50) | Mã sản phẩm (PK) |
| `Tên hàng` | `ten_hang` | VARCHAR(255) | Tên sản phẩm |
| `Giá bán` | `gia_ban_mac_dinh` | FLOAT | ✅ Giá bán mặc định |
| `Giá vốn` | `gia_von_mac_dinh` | FLOAT | ✅ Giá vốn mặc định |
| `Quy đổi` | `quy_doi` | INTEGER | **⭐ Tỉ lệ quy đổi ĐVT** |
| `Nhóm hàng(3 Cấp)` | `cap_1/cap_2/cap_3` | VARCHAR(100) | Phân loại 3 cấp |
| `ĐVT` | `don_vi_tinh` | VARCHAR(50) | Đơn vị tính |
| - | `created_at` | TIMESTAMP | Thờigian tạo |

**Status:** 15,993 products, 15,936 có giá (avg 376k)

**Ví dụ quy cách:**
| Mã hàng | Tên | Quy đổi | Ý nghĩa |
|---------|-----|---------|---------|
| 16000109 | Cốc giấy đỏ | 1 | Đơn vị lẻ |
| 16000109-1 | Cốc giấy đỏ | 50 | Lốc 50 cái |
| 16000109-2 | Cốc giấy đỏ | 1200 | Thùng 1200 cái |

#### 📄 BaoCaoBanHang.xlsx → PostgreSQL.transactions + transaction_details

**Sheet 1: Transactions (Giao dịch)**

| Excel Column | PostgreSQL Column | Data Type | Description |
|--------------|-------------------|-----------|-------------|
| `Mã giao dịch` | `ma_giao_dich` | VARCHAR(50) | Mã giao dịch |
| `Thờigian` | `ngay` | DATE | Ngày giao dịch |
| `Chi nhánh` | `ma_chi_nhanh` | VARCHAR(50) | Mã chi nhánh |
| `Tổng tiền` | `tong_tien_hang` | FLOAT | Tổng tiền hàng |
| `Giảm giá` | `giam_gia` | FLOAT | Giảm giá |
| `Doanh thu` | `doanh_thu` | FLOAT | Doanh thu |
| - | `id` | SERIAL | Auto-generated PK |

**Status:** 7,518 transactions (158 ngày)

**Sheet 2: Transaction Details (Chi tiết)**

| Excel Column | PostgreSQL Column | Data Type | Description |
|--------------|-------------------|-----------|-------------|
| `Mã giao dịch` | `transaction_id` | INT | FK → transactions.id |
| `Mã hàng` | `ma_hang` | VARCHAR(50) | Mã sản phẩm |
| `Tên hàng` | `ten_hang` | VARCHAR(255) | Tên sản phẩm |
| `Số lượng` | `so_luong` | FLOAT | Số lượng bán |
| `Đơn giá` | `don_gia` | FLOAT | ✅ Đơn giá từ file |
| `Chiết khấu` | `chiet_khau` | FLOAT | Chiết khấu |
| `Thuế GTGT` | `thue_gtgt` | FLOAT | Thuế |
| `Thành tiền` | `thanh_tien` | FLOAT | Thành tiền |
| - | `id` | SERIAL | Auto-generated PK |

**Status:** 16,293 transaction details

#### 📦 **BaoCaoXuatNhapTon.xlsx → ClickHouse.staging_inventory_transactions** ⭐ BYPASS PG

**⚠️ LƯU Ý:** Inventory import **trực tiếp** vào ClickHouse, bypass PostgreSQL

| Excel Column | ClickHouse Column | Data Type | Description |
|--------------|-------------------|-----------|-------------|
| `Nhóm hàng` | `nhom_hang` | String | Category path |
| `Mã hàng` | `ma_hang` | String | Mã sản phẩm |
| `Mã vạch` | `ma_vach` | String | Barcode |
| `Tên hàng` | `ten_hang` | String | Tên sản phẩm |
| `Thương hiệu` | `thuong_hieu` | String | Brand |
| `Đơn vị tính` | `don_vi_tinh` | String | Unit |
| `Chi nhánh` | `chi_nhanh` | String | Branch |
| **`Tồn đầu kì`** | **`ton_dau_ky`** | **Float64** | **🔢 Opening stock** |
| `Giá trị đầu kì` | `gia_tri_dau_ky` | Float64 | Opening value |
| **`SL Nhập`** | **`sl_nhap`** | **Float64** | **🔢 Quantity imported** |
| `Giá trị nhập` | `gia_tri_nhap` | Float64 | Import value |
| **`SL xuất`** | **`sl_xuat`** | **Float64** | **🔢 Quantity sold** |
| `Giá trị xuất` | `gia_tri_xuat` | Float64 | Export value |
| **`Tồn cuối kì`** | **`ton_cuoi_ky`** | **Float64** | **🔢 Closing stock** |
| `Giá trị cuối kì` | `gia_tri_cuoi_ky` | Float64 | Closing value |
| - | `snapshot_date` | Date | Ngày báo cáo |
| - | `source_file` | String | Tên file nguồn |
| - | `created_at` | DateTime64(6) | Thờigian import |

**Status:** 2,176 sản phẩm có dữ liệu tồn kho

**Engine:** MergeTree() ORDER BY (snapshot_date, ma_hang, chi_nhanh)

---

### Layer 2: PostgreSQL → ClickHouse Staging

#### 🐘 PostgreSQL.products → 🏠 ClickHouse.staging_products

| PostgreSQL | ClickHouse | Data Type | Transform |
|------------|------------|-----------|-----------|
| `id` | `id` | Int32 | Direct |
| `ma_hang` | `ma_hang` | String | Direct |
| `ten_hang` | `ten_hang` | Nullable(String) | Direct |
| `don_vi_tinh` | `don_vi_tinh` | Nullable(String) | Direct |
| `cap_1` | `cap_1` | Nullable(String) | Direct |
| `cap_2` | `cap_2` | Nullable(String) | Direct |
| `cap_3` | `cap_3` | Nullable(String) | Direct |
| `created_at` | `created_at` | Nullable(DateTime64(6)) | Direct |
| `gia_ban_mac_dinh` | `gia_ban_mac_dinh` | Nullable(Float64) | ✅ Direct (376k avg) |
| `gia_von_mac_dinh` | `gia_von_mac_dinh` | Nullable(Float64) | ✅ Direct |

**Sync Method:** `CREATE TABLE ... AS SELECT * FROM postgresql(...)`

#### 🐘 PostgreSQL.transactions → 🏠 ClickHouse.staging_transactions

| PostgreSQL | ClickHouse | Data Type | Transform |
|------------|------------|-----------|-----------|
| `id` | `id` | Int64 | Direct |
| `ma_giao_dich` | `ma_giao_dich` | String | Direct |
| `ngay` | `ngay` | String → Date | Direct |
| `ma_chi_nhanh` | `ma_chi_nhanh` | String | Direct |
| `ten_chi_nhanh` | `ten_chi_nhanh` | String | Direct |

**Status:** 7,518 rows, 158 unique dates (2025-09-11 → 2026-02-15)

#### 🐘 PostgreSQL.transaction_details → 🏠 ClickHouse.staging_transaction_details

**⚠️ CUSTOM FIX APPLIED:** Giá được lookup từ `product_prices`

| PostgreSQL | ClickHouse | Data Type | Transform |
|------------|------------|-----------|-----------|
| `id` | `id` | Int32 | Direct |
| `transaction_id` | `giao_dich_id` | Int32 | Renamed |
| 0 | `product_id` | UInt8 | Default 0 |
| `ma_hang` | `ma_hang` | String | Direct |
| `ten_hang` | `ten_hang` | String | Direct |
| `so_luong` | `so_luong` | Float64 | Direct |
| `don_gia` | `don_gia` | Float64 | Backup price |
| `chiet_khau` | `chiet_khau` | Float64 | Direct |
| `thue_gtgt` | `thue_gtgt` | Float64 | Direct |

**Price Mapping (Custom Fix):**
```sql
-- JOIN với product_prices để lấy giá đúng
gia_ban = COALESCE(product_prices.gia_ban_mac_dinh, td.don_gia, 0)
gia_von = COALESCE(product_prices.gia_von_mac_dinh, 0)
loi_nhuan = so_luong * gia_ban  -- line_revenue
```

**Status:** 16,293 rows, 16,151 có giá (avg 22,701)

#### 🐘 **PostgreSQL.inventory_transactions → 🏠 ClickHouse.staging_inventory_transactions** ⭐ NEW

| PostgreSQL | ClickHouse | Data Type | Transform |
|------------|------------|-----------|-----------|
| `id` | `id` | Int32 | Direct |
| `ma_hang` | `ma_hang` | String | Direct |
| `ten_hang` | `ten_hang` | String | Direct |
| `nhom_hang` | `nhom_hang` | String | Direct |
| `ma_vach` | `ma_vach` | String | Direct |
| `thuong_hieu` | `thuong_hieu` | String | Direct |
| `don_vi_tinh` | `don_vi_tinh` | String | Direct |
| `chi_nhanh` | `chi_nhanh` | String | Direct |
| **`ton_dau_ky`** | **`ton_dau_ky`** | **Float64** | **🔢 Opening** |
| **`sl_nhap`** | **`sl_nhap`** | **Float64** | **🔢 Import qty** |
| **`sl_xuat`** | **`sl_xuat`** | **Float64** | **🔢 Export qty** |
| **`ton_cuoi_ky`** | **`ton_cuoi_ky`** | **Float64** | **🔢 Closing** |
| `gia_tri_dau_ky` | `gia_tri_dau_ky` | Float64 | Value |
| `gia_tri_nhap` | `gia_tri_nhap` | Float64 | Value |
| `gia_tri_xuat` | `gia_tri_xuat` | Float64 | Value |
| `gia_tri_cuoi_ky` | `gia_tri_cuoi_ky` | Float64 | Value |
| `snapshot_date` | `snapshot_date` | Date | Date |

**Status:** 2,176 rows

---

### Layer 3: Staging → DBT Staging Views

#### 🏠 staging_products → 👁️ stg_products

| Staging | DBT View | Transform |
|---------|----------|-----------|
| `id` | `product_id` | Renamed |
| `ma_hang` | `product_code` | Renamed |
| `ten_hang` | `product_name` | Renamed |
| `cap_1` | `category_level_1` | Renamed |
| `cap_2` | `category_level_2` | Renamed |
| `cap_3` | `category_level_3` | Renamed |
| `gia_ban_mac_dinh` | `default_selling_price` | Renamed |
| `gia_von_mac_dinh` | `default_cost_price` | Renamed |

**Calculated Fields:**
- `default_margin_rate = (gia_ban - gia_von) / gia_ban`
- `price_tier = CASE WHEN gia_ban >= 1000000 THEN 'Premium' ...`
- `abc_class = ABC classification based on revenue`

#### 🏠 staging_transactions → 👁️ stg_transactions

| Staging | DBT View | Transform |
|---------|----------|-----------|
| `id` | `transaction_id` | toString(id) |
| `ma_giao_dich` | `transaction_code` | Direct |
| `ngay` | `transaction_date` | toDate(ngay) |
| `ma_chi_nhanh` | `branch_code` | Direct |
| `ten_chi_nhanh` | `branch_name` | Direct |

**Calculated Fields:**
- `year = toYear(transaction_date)`
- `month = toMonth(transaction_date)`
- `day_of_week = toDayOfWeek(transaction_date)`
- `hour_of_day = toHour(transaction_timestamp)`

#### 🏠 staging_transaction_details → 👁️ stg_transaction_details

| Staging | DBT View | Transform |
|---------|----------|-----------|
| `id` | `detail_id` | Direct |
| `giao_dich_id` | `transaction_id` | toString |
| `ma_hang` | `product_code` | Direct |
| `ten_hang` | `product_name` | Direct |
| `so_luong` | `quantity` | Direct |
| `gia_ban` | `selling_price` | Direct |
| `gia_von` | `cost_price` | Direct |
| `loi_nhuan` | `line_revenue` | Direct |
| `so_luong * gia_von` | `line_cost` | Calculated |
| `loi_nhuan - line_cost` | `line_profit` | Calculated |

#### 🏠 **staging_inventory_transactions → 👁️ stg_inventory_transactions** ⭐ NEW

| Staging | DBT View | Transform |
|---------|----------|-----------|
| `id` | `inventory_id` | Direct |
| `ma_hang` | `product_code` | Direct |
| `ten_hang` | `product_name` | Direct |
| `nhom_hang` | `category_path` | Direct |
| `chi_nhanh` | `branch_name` | Direct |
| `ton_dau_ky` | `opening_stock` | Direct |
| `sl_nhap` | `quantity_imported` | Direct |
| `sl_xuat` | `quantity_exported` | Direct |
| `ton_cuoi_ky` | `closing_stock` | Direct |
| `snapshot_date` | `inventory_date` | Direct |

**Calculated Fields:**
- `inventory_turnover = sl_xuat / NULLIF((ton_dau_ky + ton_cuoi_ky) / 2, 0)`
- `days_of_inventory = ton_cuoi_ky / NULLIF(sl_xuat / 30, 0)`
- `stock_to_sales_ratio = ton_cuoi_ky / NULLIF(sl_xuat, 0)`

---

### Layer 4: DBT Staging → Fact Tables

#### 👁️ stg_transaction_details + stg_transactions + dim_product → 📊 fct_regular_sales

| Source | Fact Table | Aggregation |
|--------|------------|-------------|
| `stg_transactions.transaction_date` | `transaction_date` | GROUP BY date |
| `stg_transaction_details.product_code` | `product_code` | GROUP BY product |
| `stg_transactions.branch_code` | `branch_code` | GROUP BY branch |
| COUNT(DISTINCT transaction_id) | `transaction_count` | Count |
| SUM(quantity) | `quantity_sold` | Sum |
| SUM(line_revenue) | `gross_revenue` | ✅ Sum |
| SUM(line_cost) | `cost_of_goods_sold` | Sum |
| SUM(line_profit) | `gross_profit` | Sum |
| AVG(selling_price) | `avg_selling_price` | Average |
| `gross_profit / gross_revenue` | `profit_margin` | Ratio |

**Current Status:**
- Rows: 13,937
- Total Revenue: 369,869,300
- Date Range: 2025-09-11 → 2026-02-15 (158 days)
- Products: 2,032 unique

#### 👁️ **stg_inventory_transactions + stg_products → 📊 fct_inventory_forecast_input** ⭐ NEW

| Source | Fact Table | Aggregation |
|--------|------------|-------------|
| `stg_inventory_transactions.inventory_date` | `snapshot_date` | GROUP BY date |
| `stg_inventory_transactions.product_code` | `product_code` | GROUP BY product |
| `stg_inventory_transactions.branch_name` | `branch_code` | GROUP BY branch |
| SUM(opening_stock) | `total_opening_stock` | Sum |
| SUM(quantity_imported) | `total_imported` | Sum |
| SUM(quantity_exported) | `total_exported` | Sum |
| SUM(closing_stock) | `total_closing_stock` | Sum |
| AVG(inventory_turnover) | `avg_turnover_rate` | Average |
| AVG(days_of_inventory) | `avg_days_inventory` | Average |

**Usage:** Inventory optimization, stockout prediction, reorder point calculation

---

## 🔗 DATA FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              🎯 PIPELINE DỮ LIỆU CHI TIẾT                                │
└─────────────────────────────────────────────────────────────────────────────────────────┘

╔═══════════════════════════════════════════════════════════════════════════════════════╗
║  LAYER 1: CSV SOURCES                                                                  ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                        ║
║  ┌─────────────────────────────┐      ┌─────────────────────────────────────────────┐ ║
║  │   DanhSachSanPham.csv       │      │   BaoCaoBanHang*.xlsx                       │ ║
║  │   (15,993 products)         │      │   (7,518 trans + 16,293 details)            │ ║
║  │                             │      │                                             │ ║
║  │   • Mã hàng  → ma_hang      │      │   • Mã giao dịch → transaction_id           │ ║
║  │   • Giá bán  → gia_ban      │      │   • Mã hàng → product_code                  │ ║
║  │   • Giá vốn  → gia_von      │      │   • Số lượng → quantity                     │ ║
║  │   • Nhóm hàng → cap_1/2/3   │      │   • Ngày → transaction_date                 │ ║
║  └──────────┬──────────────────┘      └────────────────────┬────────────────────────┘ ║
║             │                                              │                          ║
║             │ PySpark ETL (etl_main.py)                    │                          ║
║             │                                              │                          ║
║             ▼                                              ▼                          ║
║  ┌─────────────────────────────────────────────────────────────┐                      ║
║  │   📦 BaoCaoXuatNhapTon*.xlsx (2,176 rows)                   │                      ║
║  │                                                             │                      ║
║  │   • Tồn đầu kì → ton_dau_ky                                 │                      ║
║  │   • SL Nhập → sl_nhap                                       │                      ║
║  │   • SL Xuất → sl_xuat                                       │                      ║
║  │   • Tồn cuối kì → ton_cuoi_ky                               │                      ║
║  └──────────┬──────────────────────────────────────────────────┘                      ║
║             │                                                                          ║
╠═════════════╪══════════════════════════════════════════════════════════════════════════╣
║  LAYER 2: POSTGRESQL (OLTP)                                                            ║
╠═════════════╪══════════════════════════════════════════════════════════════════════════╣
║             │                                                                          ║
║   ┌─────────┴──────────────┐    ┌──────────────────┐    ┌────────────────────────┐     ║
║   │      products          │    │   transactions   │    │  transaction_details   │     ║
║   │      (15,993)          │    │     (7,518)      │    │       (16,293)         │     ║
║   │                        │    │                  │    │                        │     ║
║   │   PK: id               │    │   PK: id         │    │   PK: id               │     ║
║   │   UK: ma_hang          │    │   FK: None       │    │   FK: transaction_id   │     ║
║   │   ✅ gia_ban_mac_dinh  │    │   Date: ngay     │    │   Ref: ma_hang         │     ║
║   │   ✅ gia_von_mac_dinh  │    │   Branch info    │    │   Price: don_gia       │     ║
║   └──────────┬─────────────┘    └────────┬─────────┘    └──────────┬─────────────┘     ║
║              │                           │                         │                  ║
║   ┌──────────┴───────────────────────────┴─────────────────────────┴─────────────┐    ║
║   │                    📦 inventory_transactions (2,176)                           │    ║
║   │                                                                              │    ║
║   │   PK: id                                                                     │    ║
║   │   🔢 ton_dau_ky / sl_nhap / sl_xuat / ton_cuoi_ky                           │    ║
║   │   UK: ma_hang + snapshot_date                                               │    ║
║   └──────────┬───────────────────────────────────────────────────────────────────┘    ║
║              │                                                                         ║
║              │ Sync to ClickHouse                                                    ║
║              │ (postgresql() function)                                               ║
║              ▼                                                                         ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║  LAYER 3: CLICKHOUSE STAGING                                                           ║
╠═══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                        ║
║   ┌──────────────────────────┐    ┌──────────────────┐    ┌────────────────────────┐  ║
║   │   staging_products       │    │ staging_transact │    │ staging_transaction_   │  ║
║   │      (15,993)            │    │ ions (7,518)     │    │ details (16,293)       │  ║
║   │                          │    │                  │    │                        │  ║
║   │   ✅ gia_ban_mac_dinh    │    │   id → PK        │    │   giao_dich_id → FK    │  ║
║   │      (avg 376k)          │    │   ngay (158 days)│    │   ma_hang → Product    │  ║
║   │   ✅ gia_von_mac_dinh    │    │   ma_chi_nhanh   │    │   ✅ gia_ban (22k avg) │  ║
║   └──────────┬───────────────┘    └────────┬─────────┘    └──────────┬─────────────┘  ║
║              │                             │                         │               ║
║              │     ┌───────────────────────┘                         │               ║
║              │     │                                                 │               ║
║              ▼     ▼                                                 ▼               ║
║   ┌────────────────────────┐                          ┌────────────────────────┐     ║
║   │   product_prices       │                          │   JOIN + SUM()         │     ║
║   │   (helper table)       │                          │                        │     ║
║   │   ma_hang → price      │                          │   loi_nhuan = so_luong │     ║
║   └──────────┬─────────────┘                          │   × gia_ban            │     ║
║              │                                         └──────────┬─────────────┘     ║
║              │                                                    │                  ║
║   ┌──────────┴────────────────────────────────────────────────────┴─────────────┐    ║
║   │                   📦 staging_inventory_transactions (2,176)                  │    ║
║   │                                                                              │    ║
║   │   🔢 ton_dau_ky / sl_nhap / sl_xuat / ton_cuoi_ky                           │    ║
║   │   chi_nhanh / ma_hang / snapshot_date                                       │    ║
║   └──────────────────────────────────────────────────────────────┬───────────────┘    ║
║                                                                  │                    ║
╠══════════════════════════════════════════════════════════════════╪════════════════════╣
║  LAYER 4: DBT MODELS                                             │                    ║
╠══════════════════════════════════════════════════════════════════╪════════════════════╣
║                                                                  │                    ║
║   ┌──────────────────────────────────────────────────────────────┘                    ║
║   │                                                                                   ║
║   ▼                                                                                   ║
║   ┌──────────────────────────────┐    ┌──────────────────────────────────────────┐   ║
║   │   fct_regular_sales          │    │   📦 fct_inventory_forecast_input        │   ║
║   │       (13,937 rows)          │    │       (2,176 rows)                       │   ║
║   │                              │    │                                          │   ║
║   │   ✅ gross_revenue = 369M    │    │   🔢 total_closing_stock                 │   ║
║   │   ✅ 158 days of data        │    │   🔢 avg_turnover_rate                   │   ║
║   │   ✅ 2,032 products          │    │   🔢 stockout_risk_score                 │   ║
║   └──────────────┬───────────────┘    └────────────────────┬─────────────────────┘   ║
║                  │                                          │                        ║
║                  │ ML Pipeline                              │ Inventory ML           ║
║                  ▼                                          ▼                        ║
╠══════════════════════════════════════════════════════════════════════════════════════╣
║  LAYER 5: ML TRAINING                                                                ║
╠══════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                      ║
║   ┌────────────────────────────────────────────────────────────────────────────┐    ║
║   │   xgboost_forecast.py                                                      │    ║
║   │                                                                            │    ║
║   │   Sales Forecasting:                                                       │    ║
║   │   • Input: 13,821 rows (after filter)                                      │    ║
║   │   • Features: lag_1/3/7/14/21/30, seasonal factors, day_of_week, etc.      │    ║
║   │   • Models: product_quantity_model, product_profit_margin_model, etc.      │    ║
║   │                                                                            │    ║
║   │   📦 Inventory Optimization (Future):                                      │    ║
║   │   • Input: 2,176 inventory snapshots                                       │    ║
║   │   • Features: turnover_rate, days_inventory, stock_coverage                 │    ║
║   │   • Models: stockout_prediction, reorder_point_optimizer                    │    ║
║   │                                                                            │    ║
║   │   Output: 7-day forecasts + inventory recommendations                      │    ║
║   └────────────────────────────────────────────────────────────────────────────┘    ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
```

---

## 📊 CURRENT DATA STATUS (2026-03-16)

### PostgreSQL

| Table | Rows | Date Range | Key Metrics |
|-------|------|------------|-------------|
| `products` | 15,993 | N/A | 15,936 có giá, avg 376k |
| `transactions` | 7,518 | 2025-09-11 → 2026-02-15 | 158 days |
| `transaction_details` | 16,293 | N/A | Raw transactions |
| **`inventory_transactions`** | **2,176** | **Snapshot** | **Tồn kho theo sản phẩm** |

### ClickHouse Staging

| Table | Rows | Key Metrics |
|-------|------|-------------|
| `staging_products` | 15,993 | Giá TB: 376k |
| `staging_transactions` | 7,518 | 158 ngày |
| `staging_transaction_details` | 16,293 | Giá TB: 22.7k, 16,151 có giá |
| `product_prices` | 15,936 | Helper table |
| **`staging_inventory_transactions`** | **2,176** | **Inventory data** |

### ClickHouse Marts

| Table | Rows | Revenue | Date Range |
|-------|------|---------|------------|
| `fct_regular_sales` | 13,937 | 369,869,300 | 158 days |
| `fct_daily_sales` | 13,937 | 369,869,300 | Same |
| **`fct_inventory_forecast_input`** | **2,176** | N/A | Inventory snapshot |

---

## 🚀 Commands

### Kiểm tra dữ liệu

```bash
# PostgreSQL
kubectl exec postgres-587844c956-fj9kc -n hasu-ml -- psql -U retail_user -d retail_db -c "
SELECT 
    'products' as table_name,
    COUNT(*) as rows,
    AVG(gia_ban_mac_dinh) as avg_price
FROM products
"

# ClickHouse
kubectl exec clickhouse-5f8f5b445c-6wqxv -n hasu-ml -- clickhouse-client -q "
SELECT 
    'fct_regular_sales' as table,
    count() as rows,
    sum(gross_revenue) as revenue
FROM retail_dw.fct_regular_sales
"
```

### Chạy ML Training

```bash
kubectl delete job ml-train -n hasu-ml --force
cat << 'EOF' | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: ml-train
  namespace: hasu-ml
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: ml
        image: annduke/hasu-ml-pipeline:latest
        command: ["python", "xgboost_forecast.py", "--mode", "train"]
        envFrom:
        - configMapRef:
            name: hasu-ml-config
        - secretRef:
            name: hasu-ml-secrets
EOF
```

---

## ⚠️ KNOWN ISSUES & FIXES

### Issue 1: Giá = 0 trong raw_transaction_details
**Root Cause:** File Excel có đơn giá = 0  
**Fix:** JOIN với `product_prices` (từ `staging_products`) để lấy giá đúng

### Issue 2: ID mismatch
**Root Cause:** `transaction_details.transaction_id` không match `transactions.id`  
**Fix:** Recreate `staging_transaction_details` với `transaction_id` đúng từ PostgreSQL

### Issue 3: ClickHouse argMax error
**Root Cause:** ClickHouse v25+ strict analyzer  
**Fix:** Bỏ `argMax()`, dùng `DISTINCT` hoặc `assumeNotNull()`

---

## 📝 NOTES

- **Last Updated:** 2026-03-16
- **ML Status:** Training running (13,821 rows, 158 days)
- **Data Quality:** 99.6% products có giá, 99.1% transaction details có giá
- **Inventory Status:** 2,176 products có dữ liệu tồn kho (đã khôi phục từ trash)
