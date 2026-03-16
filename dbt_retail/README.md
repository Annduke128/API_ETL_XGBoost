# 🔄 DBT Retail Analytics

DBT project cho Retail Data Pipeline - Transform dữ liệu từ ClickHouse staging sang Data Warehouse.

---

## 📚 Tài liệu

| Tài liệu | Mô tả |
|----------|-------|
| **[DBT_WORKFLOW.md](DBT_WORKFLOW.md)** | 🔥 **ĐỌC TRƯỚC** - Tổng quan pipeline, schema chi tiết, data flow |
| **[DBT_QUICK_REFERENCE.md](DBT_QUICK_REFERENCE.md)** | Hướng dẫn nhanh, common issues |
| [PIPELINE_MAP.md](../PIPELINE_MAP.md) | Tổng quan toàn bộ hệ thống |
| [AGENTS.md](../AGENTS.md) | Hướng dẫn cho AI agents |

---

## 🏗️ Project Structure

```
dbt_retail/
├── models/
│   ├── staging/           # Views - làm sạch cơ bản
│   │   ├── stg_products.sql
│   │   ├── stg_transactions.sql
│   │   ├── stg_transaction_details.sql
│   │   ├── stg_branches.sql
│   │   └── sources.yml    # Định nghĩa sources
│   ├── intermediate/      # Ephemeral models
│   │   ├── int_product_performance.sql
│   │   └── int_branch_performance.sql
│   └── marts/            # Fact & Dimension tables
│       ├── sales/
│       │   ├── fct_daily_sales.sql
│       │   ├── fct_regular_sales.sql ⭐ (ML source)
│       │   └── fct_monthly_sales.sql
│       ├── products/
│       │   └── int_product_abc_classification.sql
│       └── core/
│           ├── dim_product.sql
│           └── dim_branch.sql
├── DBT_WORKFLOW.md       # ⭐ Tài liệu kỹ thuật chính
└── profiles.yml          # Kết nối ClickHouse
```

---

## 🚀 Quick Start

### Chạy DBT Build

```bash
# Cách 1: Dùng Make (từ root)
make k3s-dbt

# Cách 2: Kubectl trực tiếp
kubectl apply -f k8s/05-ml-pipeline/job-dbt-build.yaml

# Xem logs
kubectl logs -f job/dbt-build -n hasu-ml
```

### Kiểm tra kết quả

```bash
# Trong ClickHouse
kubectl exec clickhouse-5f8f5b445c-6wqxv -n hasu-ml -- clickhouse-client -q "
SELECT 
    'fct_regular_sales' as table,
    count() as rows,
    sum(gross_revenue) as revenue
FROM retail_dw.fct_regular_sales
"
```

---

## ⚠️ Quan trọng

**Trước khi sửa models:**

1. ⭐ **ĐỌC [DBT_WORKFLOW.md](DBT_WORKFLOW.md)**
2. Kiểm tra schema ClickHouse thực tế
3. Đảm bảo match với PySpark ETL output
4. Test trên K3s trước khi commit

**Schema đã thay đổi từ phiên bản cũ:**
- `giao_dich_id` → `transaction_id`
- `thoi_gian` → `ngay`
- `chi_nhanh_id` → `ma_chi_nhanh`
- `gia_ban` → `don_gia`

---

## 🔗 Dependencies

```
Staging Tables (ClickHouse)
    ↓
DBT Staging Models (Views)
    ↓
Intermediate Models
    ↓
Marts Tables (Fact & Dim)
    ↓
ML Pipeline (XGBoost)
```

---

## 📝 Notes

- **Target:** ClickHouse 24.x
- **Materialization:** Table cho marts, View cho staging
- **Partition:** Theo tháng (`toYYYYMM(date)`) cho fact tables
- **Engine:** MergeTree()

---

**Last Updated:** 2026-03-16
