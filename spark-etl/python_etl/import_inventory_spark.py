#!/usr/bin/env python3
"""
PySpark ETL: Import Inventory from Excel to PostgreSQL
Parallel processing with Spark for faster imports
"""

import os
import sys
import re
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, lit, current_timestamp, coalesce, trim, when,
    to_date, regexp_extract, input_file_name
)
from pyspark.sql.types import *


def parse_date_from_filename(filename):
    """Extract date from filename like BaoCaoXuatNhapTon_KV06032026"""
    match = re.search(r'KV(\d{2})(\d{2})(\d{4})', filename)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"
    return datetime.now().strftime('%Y-%m-%d')


def clean_numeric(value):
    """Clean numeric value"""
    if value is None:
        return 0
    try:
        return float(str(value).replace(',', '').replace('"', '').strip())
    except:
        return 0


def import_inventory(spark, file_path):
    """Import inventory using PySpark"""
    
    filename = os.path.basename(file_path)
    ngay_bao_cao = parse_date_from_filename(filename)
    week_year = datetime.strptime(ngay_bao_cao, '%Y-%m-%d').strftime('%Y-%W')
    
    print(f"🔥 [SPARK] Processing: {filename}")
    print(f"📅 Date: {ngay_bao_cao}")
    
    # Read Excel
    import pandas as pd
    
    print("📖 Reading Excel file...")
    pandas_df = pd.read_excel(file_path, sheet_name=0)
    total_rows = len(pandas_df)
    print(f"📊 Total rows: {total_rows:,}")
    
    # Convert to Spark DataFrame
    df = spark.createDataFrame(pandas_df)
    
    # Define column mappings
    column_mapping = {
        'Nhóm hàng': 'nhom_hang',
        'Mã hàng': 'ma_hang',
        'Mã vạch': 'ma_vach',
        'Tên hàng': 'ten_hang',
        'Thương hiệu': 'thuong_hieu',
        'Đơn vị tính': 'don_vi_tinh',
        'Chi nhánh': 'chi_nhanh',
        'Tồn đầu kì': 'ton_dau_ky',
        'Giá trị đầu kì': 'gia_tri_dau_ky',
        'SL Nhập': 'sl_nhap',
        'Giá trị nhập': 'gia_tri_nhap',
        'SL xuất': 'sl_xuat',
        'Giá trị xuất': 'gia_tri_xuat',
        'Tồn cuối kì': 'ton_cuoi_ky',
        'Giá trị cuối kì': 'gia_tri_cuoi_ky',
    }
    
    # Rename columns
    for old_col, new_col in column_mapping.items():
        if old_col in pandas_df.columns:
            df = df.withColumnRenamed(old_col, new_col)
    
    # Clean numeric columns with UDF (parallel)
    from pyspark.sql.functions import udf
    clean_numeric_udf = udf(clean_numeric, DoubleType())
    
    numeric_cols = ['ton_dau_ky', 'gia_tri_dau_ky', 'sl_nhap', 'gia_tri_nhap',
                    'sl_xuat', 'gia_tri_xuat', 'ton_cuoi_ky', 'gia_tri_cuoi_ky']
    
    for col_name in numeric_cols:
        if col_name in [c.lower().replace(' ', '_') for c in pandas_df.columns]:
            df = df.withColumn(col_name, clean_numeric_udf(col(col_name)))
    
    # Clean string columns
    string_cols = ['nhom_hang', 'ma_hang', 'ma_vach', 'ten_hang', 'thuong_hieu', 'don_vi_tinh', 'chi_nhanh']
    for col_name in string_cols:
        if col_name in df.columns:
            df = df.withColumn(col_name, coalesce(col(col_name).cast("string"), lit("")))
    
    # Add metadata
    df = df.withColumn('ngay_bao_cao', lit(ngay_bao_cao).cast('date'))
    df = df.withColumn('week_year', lit(week_year))
    df = df.withColumn('source_file', lit(filename))
    df = df.withColumn('created_at', current_timestamp())
    
    # Filter out rows without ma_vach
    df = df.filter((col('ma_vach').isNotNull()) & (trim(col('ma_vach')) != ''))
    
    count = df.count()
    print(f"✅ After filtering: {count:,} rows")
    
    # Select final columns
    final_cols = ['ngay_bao_cao', 'week_year', 'nhom_hang', 'ma_hang', 'ma_vach',
                  'ten_hang', 'thuong_hieu', 'don_vi_tinh', 'chi_nhanh',
                  'ton_dau_ky', 'gia_tri_dau_ky', 'sl_nhap', 'gia_tri_nhap',
                  'sl_xuat', 'gia_tri_xuat', 'ton_cuoi_ky', 'gia_tri_cuoi_ky',
                  'source_file', 'created_at']
    
    df = df.select([c for c in final_cols if c in df.columns])
    
    # Write to PostgreSQL - use UPSERT to handle duplicates
    print("💾 Writing to PostgreSQL (via pandas with UPSERT)...")
    
    import psycopg2
    from psycopg2.extras import execute_values
    
    pandas_df = df.toPandas()
    
    # Deduplicate based on the unique constraint columns
    pandas_df = pandas_df.drop_duplicates(subset=['ma_vach', 'chi_nhanh', 'ngay_bao_cao'], keep='first')
    
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'postgres'),
        database=os.getenv('POSTGRES_DB', 'retail_db'),
        user=os.getenv('POSTGRES_USER', 'retail_user'),
        password=os.getenv('POSTGRES_PASSWORD', 'retail_password')
    )
    
    try:
        with conn.cursor() as cur:
            values = [tuple(row) for row in pandas_df.values]
            columns = list(pandas_df.columns)
            
            # Build UPSERT query for inventory_transactions
            # Unique constraint: (ma_vach, chi_nhanh, ngay_bao_cao)
            update_cols = [c for c in columns if c not in ['ma_vach', 'chi_nhanh', 'ngay_bao_cao']]
            update_stmt = ', '.join([f"{c} = EXCLUDED.{c}" for c in update_cols])
            
            query = f"""
                INSERT INTO inventory_transactions ({', '.join(columns)}) 
                VALUES %s 
                ON CONFLICT (ma_vach, chi_nhanh, ngay_bao_cao) DO UPDATE SET {update_stmt}
            """
            
            execute_values(cur, query, values)
            conn.commit()
    finally:
        conn.close()
    
    print(f"✅ Imported {count:,} inventory records to PostgreSQL")
    
    # Write to ClickHouse for ML processing
    print("💾 Writing to ClickHouse staging for ML...")
    try:
        ch_host = os.getenv('CLICKHOUSE_HOST', 'clickhouse')
        ch_db = os.getenv('CLICKHOUSE_DB', 'retail_dw')
        ch_user = os.getenv('CLICKHOUSE_USER', 'default')
        ch_pass = os.getenv('CLICKHOUSE_PASSWORD', 'clickhouse_password')
        
        ch_url = f"jdbc:clickhouse://{ch_host}:8123/{ch_db}?user={ch_user}&password={ch_pass}"
        ch_props = {
            "driver": "com.clickhouse.jdbc.ClickHouseDriver"
        }
        
        # Write to ClickHouse - overwrite mode to handle duplicates
        df.write \
            .mode("overwrite") \
            .option("createTableOptions", "ENGINE = MergeTree() ORDER BY (ngay_bao_cao, ma_vach, chi_nhanh)") \
            .jdbc(ch_url, "staging_inventory_transactions", properties=ch_props)
        
        print(f"✅ Imported {count:,} inventory records to ClickHouse for ML")
    except Exception as e:
        print(f"⚠️  ClickHouse write skipped: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"✅ Total imported: {count:,} rows")
    print(f"📅 Date: {ngay_bao_cao}")
    print(f"📦 Unique products: {df.select('ma_vach').distinct().count():,}")
    print("=" * 70)
    
    return count


def main():
    if len(sys.argv) < 2:
        print("Usage: spark-submit import_inventory_spark.py <excel_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        sys.exit(1)
    
    spark = SparkSession.builder \
        .appName("ImportInventory-Spark") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.jars", "/opt/spark/jars/postgresql-42.6.0.jar,/opt/spark/jars/clickhouse-jdbc-0.6.0-all.jar") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    print("=" * 70)
    print("🔥 PYSPARK ETL: Import Inventory")
    print("=" * 70)
    
    try:
        count = import_inventory(spark, file_path)
        
        print("\n" + "=" * 70)
        print(f"✅ SUCCESS: Imported {count:,} inventory records using Spark")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
