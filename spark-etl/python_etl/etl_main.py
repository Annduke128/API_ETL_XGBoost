#!/usr/bin/env python3
"""
PySpark ETL Pipeline - Logic từ data_cleaning đã chuyển sang PySpark
- import_products: UPSERT (ON CONFLICT UPDATE), parse nhóm hàng 3 cấp
- import_sales: UPSERT (ON CONFLICT DO NOTHING), aggregate transactions
"""

import os
import re
import logging
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    udf,
    col, lit, current_timestamp, coalesce, trim, sum as spark_sum, expr
)
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CSV_INPUT = '/csv_input'

# UDFs từ data_cleaning
@udf(returnType=StructType([
    StructField("cap_1", StringType(), True),
    StructField("cap_2", StringType(), True),
    StructField("cap_3", StringType(), True)
]))
def parse_nhom_hang_udf(nhom_hang_str):
    """Parse nhóm hàng 3 cấp - logic từ data_cleaning"""
    if not nhom_hang_str or str(nhom_hang_str).strip() == '':
        return ('', '', '')
    parts = str(nhom_hang_str).split('>>')
    return (
        parts[0].strip() if len(parts) > 0 else '',
        parts[1].strip() if len(parts) > 1 else '',
        parts[2].strip() if len(parts) > 2 else ''
    )

@udf(returnType=DoubleType())
def clean_numeric_udf(value):
    """Clean numeric - logic từ data_cleaning"""
    if value is None:
        return 0.0
    try:
        s = str(value).replace(',', '').replace('"', '').strip()
        return float(s) if s else 0.0
    except:
        return 0.0

@udf(returnType=IntegerType())
def calculate_conversion_ratio(dvt, product_name):
    """Calculate conversion ratio based on unit type (ĐVT)
    
    Logic:
    - thùng/thung/carton → 6, 12, 24 (box)
    - lốc/loc → 6, 12, 24 (pack)
    - can/chai/gói/cái/bịch → 1 (single)
    - hộp/hop → 1 hoặc 12
    """
    if not dvt:
        return 1
    
    dvt_lower = str(dvt).lower().strip()
    name_lower = str(product_name).lower() if product_name else ""
    
    # Box units (thùng)
    if any(x in dvt_lower for x in ['thùng', 'thung', 'carton', 'thung carton']):
        # Check if product name contains quantity hints
        if 'x24' in name_lower or 'x 24' in name_lower:
            return 24
        elif 'x12' in name_lower or 'x 12' in name_lower:
            return 12
        elif 'x6' in name_lower or 'x 6' in name_lower:
            return 6
        else:
            return 6  # Default for box
    
    # Pack units (lốc)
    if any(x in dvt_lower for x in ['lốc', 'loc', 'pack']):
        if 'x24' in name_lower or 'x 24' in name_lower:
            return 24
        elif 'x12' in name_lower or 'x 12' in name_lower:
            return 12
        elif 'x6' in name_lower or 'x 6' in name_lower:
            return 6
        else:
            return 6  # Default for pack
    
    # Single units
    if any(x in dvt_lower for x in ['can', 'chai', 'gói', 'goi', 'cái', 'cai', 'bịch', 'bich', 'hũ', 'hu']):
        return 1
    
    # Box/Container - check quantity
    if 'hộp' in dvt_lower or 'hop' in name_lower:
        if 'x12' in name_lower or 'x 12' in name_lower:
            return 12
        return 1
    
    return 1  # Default

def get_spark_session():
    return SparkSession.builder \
        .appName("Retail_ETL") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .config("spark.jars", "/opt/spark/jars/postgresql-42.6.0.jar,/opt/spark/jars/clickhouse-jdbc-0.6.0-all.jar") \
        .getOrCreate()

def parse_date_from_filename(filename):
    match = re.search(r'KV(\d{2})(\d{2})(\d{4})', filename)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"
    return datetime.now().strftime('%Y-%m-%d')

def read_csv_with_pandas_bridge(spark, file_path):
    import pandas as pd
    if file_path.endswith('.csv'):
        pdf = pd.read_csv(file_path, encoding='utf-8-sig', dtype=str)
    else:
        pdf = pd.read_excel(file_path, dtype=str)
    return spark.createDataFrame(pdf)

def process_products_pyspark(spark):
    import glob
    files = glob.glob(f"{CSV_INPUT}/*DanhSachSanPham*.csv") + glob.glob(f"{CSV_INPUT}/*DanhSachSanPham*.xlsx")
    if not files:
        logger.warning("⚠️ No products file")
        return
    
    file_path = files[0]
    logger.info(f"📦 Products: {os.path.basename(file_path)}")
    
    df = read_csv_with_pandas_bridge(spark, file_path)
    
    col_map = {}
    for c in df.columns:
        lc = c.lower()
        if 'mã' in lc and 'hàng' in lc:
            col_map['ma_hang'] = c
        elif 'tên' in lc and 'hàng' in lc:
            col_map['ten_hang'] = c
        elif 'đvt' in lc or 'đơn vị' in lc:
            col_map['don_vi_tinh'] = c
        elif 'nhóm' in lc and 'cấp' in lc:
            col_map['nhom_hang'] = c
        elif 'giá vốn' in lc:
            col_map['gia_von'] = c
        elif 'giá bán' in lc:
            col_map['gia_ban'] = c
        elif 'mã vạch' in lc:
            col_map['ma_vach'] = c
        elif 'quy' in lc and 'đổi' in lc:
            col_map['quy_doi'] = c
        # INVENTORY columns from DanhSachSanPham
        elif 'tồn' in lc and ('kho' in lc or 'hiện tại' in lc or 'current' in lc):
            col_map['current_stock'] = c
        elif 'tồn' in lc and ('nhỏ' in lc or 'tối thiểu' in lc or 'min' in lc):
            col_map['min_stock'] = c
        elif 'tồn' in lc and ('lớn' in lc or 'tối đa' in lc or 'max' in lc):
            col_map['max_stock'] = c
    
    # DEBUG: Log column mapping for inventory
    logger.info(f"DEBUG col_map inventory: current_stock={col_map.get('current_stock', 'NOT FOUND')}, min_stock={col_map.get('min_stock', 'NOT FOUND')}, max_stock={col_map.get('max_stock', 'NOT FOUND')}")
    
    # DEBUG: Check raw values from DataFrame
    current_stock_col = col_map.get('current_stock')
    min_stock_col = col_map.get('min_stock')
    logger.info(f"DEBUG current_stock_col name: {repr(current_stock_col)}")
    logger.info(f"DEBUG min_stock_col name: {repr(min_stock_col)}")
    
    # Sample raw values
    sample_rows = df.select(current_stock_col, min_stock_col).limit(5).collect()
    for i, row in enumerate(sample_rows):
        logger.info(f"DEBUG Row {i}: current_stock={repr(row[0])}, min_stock={repr(row[1])}")
    
    # Clean numeric columns for prices
    df_with_prices = df.select(
        trim(col(col_map.get('ma_hang', df.columns[0]))).alias("ma_hang"),
        coalesce(trim(col(col_map.get('ten_hang', df.columns[0]))), lit('')).alias("ten_hang"),
        coalesce(trim(col(col_map.get('don_vi_tinh', df.columns[0]))), lit('')).alias("don_vi_tinh"),
        col(col_map.get('nhom_hang', df.columns[0])).alias("nhom_hang_raw"),
        # Add price columns with cleaning
        clean_numeric_udf(col(col_map.get('gia_ban', lit('0')))).alias("gia_ban_mac_dinh"),
        clean_numeric_udf(col(col_map.get('gia_von', lit('0')))).alias("gia_von_mac_dinh"),
        # Add quy_doi column (default 1 if not present)
        clean_numeric_udf(col(col_map.get('quy_doi', lit('1')))).cast("int").alias("quy_doi"),
        # INVENTORY columns from DanhSachSanPham
        # Use expr with backticks for column names with spaces
        clean_numeric_udf(expr(f"`{col_map.get('current_stock', '0')}`")).cast("double").alias("current_stock"),
        clean_numeric_udf(expr(f"`{col_map.get('min_stock', '0')}`")).cast("int").alias("min_stock"),
        clean_numeric_udf(expr(f"`{col_map.get('max_stock', '0')}`")).cast("int").alias("max_stock"),
        current_timestamp().alias("created_at")
    )
    
    df_parsed = df_with_prices.withColumn("nhom_parsed", parse_nhom_hang_udf(col("nhom_hang_raw")))
    
    df_final = df_parsed.select(
        col("ma_hang"), col("ten_hang"), col("don_vi_tinh"),
        col("nhom_parsed.cap_1").alias("cap_1"),
        col("nhom_parsed.cap_2").alias("cap_2"),
        col("nhom_parsed.cap_3").alias("cap_3"),
        col("gia_ban_mac_dinh"),
        col("gia_von_mac_dinh"),
        col("quy_doi"),
        # INVENTORY columns from DanhSachSanPham
        col("current_stock"),
        col("min_stock"),
        col("max_stock"),
        col("created_at")
    ).dropDuplicates(["ma_hang"])
    
    count = df_final.count()
    logger.info(f"   ✅ {count} products")
    
    # DEBUG: Count inventory stats
    from pyspark.sql.functions import sum as spark_sum, count as spark_count, when
    stock_stats = df_final.agg(
        spark_sum("current_stock").alias("total_stock"),
        spark_count(when(col("current_stock") > 0, 1)).alias("products_with_stock"),
        spark_sum("min_stock").alias("total_min_stock"),
        spark_count(when(col("min_stock") > 0, 1)).alias("products_with_min_stock")
    ).collect()[0]
    logger.info(f"   DEBUG: total_stock={stock_stats['total_stock']}, products_with_stock={stock_stats['products_with_stock']}")
    logger.info(f"   DEBUG: total_min_stock={stock_stats['total_min_stock']}, products_with_min_stock={stock_stats['products_with_min_stock']}")
    
    pg_url = f"jdbc:postgresql://{os.getenv('POSTGRES_HOST','postgres')}:5432/{os.getenv('POSTGRES_DB','retail_db')}"
    pg_props = {
        "user": os.getenv("POSTGRES_USER","retail_user"),
        "password": os.getenv("POSTGRES_PASSWORD","retail_password"),
        "driver": "org.postgresql.Driver"
    }
    
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST','postgres'),
        database=os.getenv('POSTGRES_DB','retail_db'),
        user=os.getenv('POSTGRES_USER','retail_user'),
        password=os.getenv('POSTGRES_PASSWORD','retail_password')
    )
    conn.autocommit = True
    with conn.cursor() as cur:
        # Add inventory columns if not exist
        cur.execute("""
            ALTER TABLE products 
            ADD COLUMN IF NOT EXISTS current_stock DOUBLE PRECISION DEFAULT 0,
            ADD COLUMN IF NOT EXISTS min_stock INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS max_stock INTEGER DEFAULT 0
        """)
    conn.close()
    
    # UPSERT products using psycopg2 (avoid TRUNCATE to preserve historical data)
    logger.info(f"   🔄 UPSERTING {count} products...")
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST','postgres'),
        database=os.getenv('POSTGRES_DB','retail_db'),
        user=os.getenv('POSTGRES_USER','retail_user'),
        password=os.getenv('POSTGRES_PASSWORD','retail_password')
    )
    conn.autocommit = True
    
    # Convert to list of tuples for upsert
    products_data = [(row['ma_hang'], row['ten_hang'], row['cap_1'], row['cap_2'], row['cap_3'], 
                      row['don_vi_tinh'], row['quy_doi'], row['thuong_hieu']) 
                     for _, row in df_final.toPandas().iterrows()]
    
    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO products (ma_hang, ten_hang, cap_1, cap_2, cap_3, don_vi_tinh, quy_doi, thuong_hieu)
            VALUES %s
            ON CONFLICT (ma_hang) DO UPDATE SET
                ten_hang = EXCLUDED.ten_hang,
                cap_1 = EXCLUDED.cap_1,
                cap_2 = EXCLUDED.cap_2,
                cap_3 = EXCLUDED.cap_3,
                don_vi_tinh = EXCLUDED.don_vi_tinh,
                quy_doi = EXCLUDED.quy_doi,
                thuong_hieu = EXCLUDED.thuong_hieu
        """, products_data)
    
    conn.close()
    logger.info(f"   ✅ UPSERTED {count} products")

def process_sales_pyspark(spark):
    import glob
    files = glob.glob(f"{CSV_INPUT}/*BaoCaoBanHang*.csv") + glob.glob(f"{CSV_INPUT}/*BaoCaoBanHang*.xlsx")
    if not files:
        logger.warning("⚠️ No sales files")
        return
    
    for file_path in files:
        filename = os.path.basename(file_path)
        ngay_bao_cao = parse_date_from_filename(filename)
        logger.info(f"💰 Sales: {filename} | Date: {ngay_bao_cao}")
        
        df = read_csv_with_pandas_bridge(spark, file_path)
        total_rows = df.count()
        logger.info(f"   📊 Rows: {total_rows}")
        
        col_ma_gd = col_chi_nhanh = col_ma_hang = col_so_luong = col_don_gia = col_thanh_tien = col_tong_tien = None
        col_thoigian = None
        for c in df.columns:
            lc = c.lower()
            if 'mã' in lc and 'giao dịch' in lc:
                col_ma_gd = c
            elif 'chi nhánh' in lc:
                col_chi_nhanh = c
            elif 'mã' in lc and 'hàng' in lc:
                col_ma_hang = c
            elif 'số lượng' in lc or lc == 'sl':
                col_so_luong = c
            elif 'đơn giá' in lc or 'giá bán/sp' in lc or 'giá bán' in lc:
                col_don_gia = c
            elif 'thành tiền' in lc or 'doanh thu' in lc:
                col_thanh_tien = c
            elif 'tổng tiền' in lc or 'tổng tiền hàng' in lc:
                col_tong_tien = c
            elif ('thờigian' in lc and 'giao dịch' in lc) or ('thờigian' in lc.replace(' ', '') and 'giao' in lc):
                col_thoigian = c
        
        if not col_ma_gd or not col_ma_hang:
            logger.warning("   ⚠️ Skip - missing columns")
            continue
        
        if col_chi_nhanh:
            branches_df = df.select(trim(col(col_chi_nhanh)).alias("ma_chi_nhanh")).distinct()
            logger.info(f"   ✅ {branches_df.count()} branches")
        
        # Dùng cột thờigian từ Excel nếu có, nếu không thì dùng ngày từ filename
        if col_thoigian:
            ngay_col = col(col_thoigian).cast("date")
            logger.info(f"   📅 Using date from Excel column: {col_thoigian}")
        else:
            ngay_col = lit(ngay_bao_cao).cast("date")
            logger.info(f"   📅 Using date from filename: {ngay_bao_cao}")
        
        trans_df = df.select(
            trim(col(col_ma_gd)).alias("ma_giao_dich"),
            trim(col(col_chi_nhanh if col_chi_nhanh else lit('Unknown'))).alias("ma_chi_nhanh"),
            ngay_col.alias("ngay")
        )
        
        trans_agg = trans_df.dropDuplicates(["ma_giao_dich"])
        trans_count = trans_agg.count()
        
        # Xử lý details với fallback cho cột thiếu
        sl_expr = clean_numeric_udf(col(col_so_luong)).cast("int") if col_so_luong else lit(1)
        dg_expr = clean_numeric_udf(col(col_don_gia)) if col_don_gia else lit(0)
        tt_expr = clean_numeric_udf(col(col_thanh_tien)) if col_thanh_tien else lit(0)
        
        details_df = df.select(
            trim(col(col_ma_gd)).alias("ma_giao_dich"),
            trim(col(col_ma_hang)).alias("ma_hang"),
            sl_expr.alias("so_luong"),
            dg_expr.alias("don_gia"),
            tt_expr.alias("thanh_tien"),
            current_timestamp().alias("created_at")
        )
        
        # Tính thanh_tien từ don_gia * so_luong thay vì dùng cột Doanh thu (theo giao dịch)
        # vì cột Doanh thu là tổng của cả giao dịch, không phải từng dòng sản phẩm
        details_df = details_df.withColumn("thanh_tien_calc", col("don_gia") * col("so_luong"))
        
        details_agg = details_df.groupBy("ma_giao_dich","ma_hang","created_at").agg(
            spark_sum("so_luong").alias("so_luong"),
            expr("avg(don_gia)").alias("don_gia"),
            spark_sum("thanh_tien_calc").alias("thanh_tien")
        )
        details_count = details_agg.count()
        
        pg_url = f"jdbc:postgresql://{os.getenv('POSTGRES_HOST','postgres')}:5432/{os.getenv('POSTGRES_DB','retail_db')}"
        pg_props = {
            "user": os.getenv("POSTGRES_USER","retail_user"),
            "password": os.getenv("POSTGRES_PASSWORD","retail_password"),
            "driver": "org.postgresql.Driver"
        }
        
        # UPSERT transactions để tránh duplicate
        logger.info("   🔄 UPSERT transactions...")
        
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST','postgres'),
            database=os.getenv('POSTGRES_DB','retail_db'),
            user=os.getenv('POSTGRES_USER','retail_user'),
            password=os.getenv('POSTGRES_PASSWORD','retail_password')
        )
        conn.autocommit = True
        
        # Chuyển trans_agg sang list
        trans_data = [(row['ma_giao_dich'], row['ma_chi_nhanh'], row['ngay']) 
                      for _, row in trans_agg.toPandas().iterrows()]
        
        with conn.cursor() as cur:
            # UPSERT transactions
            execute_values(cur, """
                INSERT INTO transactions (ma_giao_dich, chi_nhanh_id, thoi_gian)
                VALUES (%s, (SELECT id FROM branches WHERE ma_chi_nhanh = %s LIMIT 1), %s)
                ON CONFLICT (ma_giao_dich, thoi_gian) DO NOTHING
            """, trans_data)
        
        conn.close()
        logger.info("   ✅ UPSERTED transactions")
        
        # Đọc lại transactions để lấy transaction_id
        trans_mapping = spark.read.jdbc(pg_url, "transactions", properties=pg_props).select("id", "ma_giao_dich")
        details_with_id = details_agg.join(trans_mapping, "ma_giao_dich").select(
            col("id").alias("transaction_id"),
            col("ma_hang"),
            col("so_luong").cast("double"),
            col("don_gia").cast("double"),
            lit(0.0).alias("chiet_khau"),
            lit(0.0).alias("thue_gtgt"),
            col("thanh_tien").cast("double")
        )
        
        # Loại bỏ duplicate trong details trước khi insert
        details_final = details_with_id.dropDuplicates(["transaction_id", "ma_hang"])
        final_count = details_final.count()
        logger.info(f"   📊 After dedup: {final_count} details (removed {details_count - final_count} duplicates)")
        
        details_final.write.jdbc(pg_url, "transaction_details", mode="append", properties=pg_props)
        logger.info(f"   ✅ {trans_count} trans, {details_count} details")

def main():
    logger.info("="*60)
    logger.info("🚀 PySpark ETL - Logic from data_cleaning")
    logger.info("="*60)
    
    spark = get_spark_session()
    try:
        process_products_pyspark(spark)  # Includes inventory data from DanhSachSanPham
        process_sales_pyspark(spark)
        logger.info("="*60)
        logger.info("✅ Complete!")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise
    finally:
        spark.stop()

if __name__ == '__main__':
    main()

