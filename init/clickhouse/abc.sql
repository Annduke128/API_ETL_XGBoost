-- ============================================
-- ABC CLASSIFICATION BASED ON REVENUE
-- ============================================

-- Drop old temp tables if exist
DROP TABLE IF EXISTS retail_dw.temp_abc_revenue;
DROP TABLE IF EXISTS retail_dw.temp_abc_total;
DROP TABLE IF EXISTS retail_dw.temp_abc_result;

-- Step 1: Calculate revenue per product
CREATE TABLE retail_dw.temp_abc_revenue
ENGINE = MergeTree()
ORDER BY product_code
AS
SELECT 
    sp.ma_hang as product_code,
    COALESCE(SUM(f.gross_revenue), 0) as revenue
FROM retail_dw.staging_products sp
LEFT JOIN retail_dw.fct_daily_sales f 
    ON sp.ma_hang = f.product_code
GROUP BY sp.ma_hang;

-- Step 2: Calculate grand total
CREATE TABLE retail_dw.temp_abc_total
ENGINE = MergeTree()
ORDER BY idx
AS
SELECT 
    sum_revenue as grand_total,
    1 as idx
FROM (
    SELECT SUM(revenue) as sum_revenue
    FROM retail_dw.temp_abc_revenue
);

-- Step 3: Calculate cumulative and assign ABC
CREATE TABLE retail_dw.temp_abc_result
ENGINE = MergeTree()
ORDER BY product_code
AS
SELECT 
    tr.product_code,
    tr.revenue,
    CASE 
        WHEN cum.cumulative / tot.grand_total * 100 <= 80 THEN 'A'
        WHEN cum.cumulative / tot.grand_total * 100 <= 95 THEN 'B'
        ELSE 'C'
    END as abc_class
FROM retail_dw.temp_abc_revenue tr
LEFT JOIN (
    SELECT 
        temp_abc_revenue.product_code as pcode,
        SUM(temp_abc_revenue.revenue) OVER (ORDER BY temp_abc_revenue.revenue DESC) as cumulative
    FROM retail_dw.temp_abc_revenue
) cum ON tr.product_code = cum.pcode
CROSS JOIN retail_dw.temp_abc_total tot;

-- Show statistics
SELECT 
    abc_class,
    count() as cnt,
    sum(revenue) as total_rev
FROM retail_dw.temp_abc_result
GROUP BY abc_class
ORDER BY abc_class;

-- Step 4: Update dim_product using JOIN (ClickHouse syntax)
-- ClickHouse không hỗ trợ UPDATE ... FROM, dùng cách khác

-- Cách 1: Tạo bảng mới với dữ liệu đã update
CREATE OR REPLACE TABLE retail_dw.dim_product_new
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY product_id
AS
SELECT 
    d.product_id,
    d.product_code,
    d.barcode,
    d.product_name,
    d.brand,
    d.category_level_1,
    d.category_level_2,
    d.category_level_3,
    d.default_cost_price,
    d.default_selling_price,
    d.default_margin_rate,
    d.price_tier,
    COALESCE(r.abc_class, d.abc_class) as abc_class,
    COALESCE(r.revenue, d.total_historical_revenue) as total_historical_revenue,
    d.total_historical_quantity,
    d.historical_profit_margin,
    d.product_status,
    d.created_at,
    now() as updated_at
FROM retail_dw.dim_product d
LEFT JOIN retail_dw.temp_abc_result r ON d.product_code = r.product_code;

-- Cách 2: Rename bảng (hoặc dùng EXCHANGE TABLES nếu có)
-- Lưu ý: Cần backup trước khi làm điều này trong production

-- Verify result
SELECT 
    abc_class,
    count() as cnt
FROM retail_dw.dim_product_new
GROUP BY abc_class
ORDER BY abc_class;

-- Cleanup temp tables
-- DROP TABLE IF EXISTS retail_dw.temp_abc_revenue;
-- DROP TABLE IF EXISTS retail_dw.temp_abc_total;
-- DROP TABLE IF EXISTS retail_dw.temp_abc_result;
