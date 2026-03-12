#!/usr/bin/env python3
"""
PySpark ETL Pipeline - Logic từ data_cleaning đã chuyển sang PySpark
- import_products: TRUNCATE + INSERT, parse nhóm hàng 3 cấp
- import_sales: DELETE by date + INSERT, aggregate transactions
"""

import os
import re
import logging
from datetime import datetime
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
    
    df_clean = df.select(
        trim(col(col_map.get('ma_hang', df.columns[0]))).alias("ma_hang"),
        coalesce(trim(col(col_map.get('ten_hang', df.columns[0]))), lit('')).alias("ten_hang"),
        coalesce(trim(col(col_map.get('don_vi_tinh', df.columns[0]))), lit('')).alias("don_vi_tinh"),
        col(col_map.get('nhom_hang', df.columns[0])).alias("nhom_hang_raw"),
        current_timestamp().alias("created_at")
    )
    
    df_parsed = df_clean.withColumn("nhom_parsed", parse_nhom_hang_udf(col("nhom_hang_raw")))
    df_final = df_parsed.select(
        col("ma_hang"), col("ten_hang"), col("don_vi_tinh"),
        col("nhom_parsed.cap_1").alias("cap_1"),
        col("nhom_parsed.cap_2").alias("cap_2"),
        col("nhom_parsed.cap_3").alias("cap_3"),
        col("created_at")
    ).dropDuplicates(["ma_hang"])
    
    count = df_final.count()
    logger.info(f"   ✅ {count} products")
    
    pg_url = f"jdbc:postgresql://{os.getenv('POSTGRES_HOST','postgres')}:5432/{os.getenv('POSTGRES_DB','retail_db')}"
    pg_props = {
        "user": os.getenv("POSTGRES_USER","retail_user"),
        "password": os.getenv("POSTGRES_PASSWORD","retail_password"),
        "driver": "org.postgresql.Driver"
    }
    
    import psycopg2
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST','postgres'),
        database=os.getenv('POSTGRES_DB','retail_db'),
        user=os.getenv('POSTGRES_USER','retail_user'),
        password=os.getenv('POSTGRES_PASSWORD','retail_password')
    )
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE products CASCADE")
    conn.close()
    
    df_final.write.jdbc(pg_url, "products", mode="append", properties=pg_props)
    logger.info(f"   ✅ Inserted {count} products")

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
            elif 'số lượng' in lc:
                col_so_luong = c
            elif 'đơn giá' in lc:
                col_don_gia = c
            elif 'thành tiền' in lc:
                col_thanh_tien = c
            elif 'tổng tiền' in lc:
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
        
        details_agg = details_df.groupBy("ma_giao_dich","ma_hang","created_at").agg(
            spark_sum("so_luong").alias("so_luong"),
            expr("avg(don_gia)").alias("don_gia"),
            spark_sum("thanh_tien").alias("thanh_tien")
        )
        details_count = details_agg.count()
        
        pg_url = f"jdbc:postgresql://{os.getenv('POSTGRES_HOST','postgres')}:5432/{os.getenv('POSTGRES_DB','retail_db')}"
        pg_props = {
            "user": os.getenv("POSTGRES_USER","retail_user"),
            "password": os.getenv("POSTGRES_PASSWORD","retail_password"),
            "driver": "org.postgresql.Driver"
        }
        
        # Không xóa dữ liệu cũ, dùng INSERT IGNORE để bỏ qua duplicate
        logger.info("   💾 Using INSERT IGNORE mode (skip duplicates)")
        
        trans_agg.write.jdbc(pg_url, "transactions", mode="ignore", properties=pg_props)
        
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
        
        details_with_id.write.jdbc(pg_url, "transaction_details", mode="append", properties=pg_props)
        logger.info(f"   ✅ {trans_count} trans, {details_count} details")

def main():
    logger.info("="*60)
    logger.info("🚀 PySpark ETL - Logic from data_cleaning")
    logger.info("="*60)
    
    spark = get_spark_session()
    try:
        process_products_pyspark(spark)
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
