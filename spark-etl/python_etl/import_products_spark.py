#!/usr/bin/env python3
"""
PySpark ETL: Import Products from Excel to PostgreSQL & ClickHouse
Tốc độ đa luồng, xử lý song song với Spark
"""

import os
import sys
import re
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, lit, current_timestamp, coalesce, trim, split,
    regexp_replace, when, input_file_name
)
from pyspark.sql.types import *


def parse_date_from_filename(filename):
    """Extract date from filename like DanhSachSanPham_KV06032026"""
    match = re.search(r'KV(\d{2})(\d{2})(\d{4})', filename)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"
    return datetime.now().strftime('%Y-%m-%d')


def clean_numeric(value):
    """Clean numeric value, handling commas"""
    if value is None:
        return 0.0
    try:
        return float(str(value).replace(',', '').replace('"', '').strip())
    except:
        return 0.0


def parse_nhom_hang(nhom_hang_str):
    """Parse 'Nhóm hàng(3 Cấp)' into 3 levels"""
    if not nhom_hang_str or str(nhom_hang_str).strip() == '':
        return '', '', ''
    
    parts = str(nhom_hang_str).split('>>')
    return (
        parts[0].strip() if len(parts) > 0 else '',
        parts[1].strip() if len(parts) > 1 else '',
        parts[2].strip() if len(parts) > 2 else ''
    )


def import_products(spark, file_path):
    """Import products using PySpark with parallel processing"""
    
    filename = os.path.basename(file_path)
    print(f"🔥 [SPARK] Processing: {filename}")
    
    # Read Excel using Spark's binaryFile + pandas UDF approach
    # For simplicity, use pandas to read then convert to Spark DF
    import pandas as pd
    
    print("📖 Reading Excel file...")
    pandas_df = pd.read_excel(file_path, engine='openpyxl')
    total_rows = len(pandas_df)
    print(f"📊 Total rows: {total_rows:,}")
    
    # Convert to Spark DataFrame for parallel processing
    df = spark.createDataFrame(pandas_df)
    
    # Parallel processing with Spark
    print("⚡ Parallel processing with Spark...")
    
    # Parse nhóm hàng using UDF
    from pyspark.sql.functions import udf
    from pyspark.sql.types import StructType, StructField, StringType
    
    nhom_hang_schema = StructType([
        StructField("cap_1", StringType(), True),
        StructField("cap_2", StringType(), True),
        StructField("cap_3", StringType(), True)
    ])
    
    parse_nhom_udf = udf(parse_nhom_hang, nhom_hang_schema)
    
    df = df.withColumn("nhom_hang_parsed", parse_nhom_udf(col("Nhóm hàng(3 Cấp)")))
    df = df.withColumn("nhom_hang_cap_1", col("nhom_hang_parsed.cap_1"))
    df = df.withColumn("nhom_hang_cap_2", col("nhom_hang_parsed.cap_2"))
    df = df.withColumn("nhom_hang_cap_3", col("nhom_hang_parsed.cap_3"))
    
    # Clean numeric columns using UDF
    clean_numeric_udf = udf(clean_numeric, DoubleType())
    
    df = df.withColumn("gia_von_clean", clean_numeric_udf(col("Giá vốn")))
    df = df.withColumn("gia_ban_clean", clean_numeric_udf(col("Giá bán")))
    
    # Select and rename columns
    df = df.select(
        col("Mã hàng").cast("string").alias("ma_hang"),
        coalesce(col("Mã vạch").cast("string"), lit("")).alias("ma_vach"),
        col("Tên hàng").cast("string").alias("ten_hang"),
        coalesce(col("Thương hiệu").cast("string"), lit("")).alias("thuong_hieu"),
        col("nhom_hang_cap_1"),
        col("nhom_hang_cap_2"),
        col("nhom_hang_cap_3"),
        col("gia_von_clean").cast("decimal(15,2)").alias("gia_von_mac_dinh"),
        col("gia_ban_clean").cast("decimal(15,2)").alias("gia_ban_mac_dinh"),
        current_timestamp().alias("created_at")
    )
    
    # Remove duplicates (parallel with Spark)
    print("🔄 Removing duplicates...")
    df = df.dropDuplicates(["ma_hang"])
    
    count = df.count()
    print(f"✅ After deduplication: {count:,} products")
    
    # Write to PostgreSQL using JDBC (parallel write)
    print("💾 Writing to PostgreSQL (parallel)...")
    
    pg_url = f"jdbc:postgresql://{os.getenv('POSTGRES_HOST', 'postgres')}:5432/{os.getenv('POSTGRES_DB', 'retail_db')}"
    pg_props = {
        "user": os.getenv("POSTGRES_USER", "retail_user"),
        "password": os.getenv("POSTGRES_PASSWORD", "retail_password"),
        "driver": "org.postgresql.Driver"
    }
    
    # Truncate and load
    df.write \
        .mode("overwrite") \
        .option("truncate", "true") \
        .jdbc(pg_url, "products", properties=pg_props)
    
    print(f"✅ Imported {count:,} products to PostgreSQL")
    
    # Write to ClickHouse
    print("💾 Writing to ClickHouse staging...")
    try:
        ch_url = f"jdbc:clickhouse://{os.getenv('CLICKHOUSE_HOST', 'clickhouse')}:8123/{os.getenv('CLICKHOUSE_DB', 'retail_dw')}"
        ch_props = {
            "driver": "com.clickhouse.jdbc.ClickHouseDriver"
        }
        
        df.write \
            .mode("overwrite") \
            .option("createTableOptions", "ENGINE = MergeTree() ORDER BY ma_hang") \
            .jdbc(ch_url, "staging_products", properties=ch_props)
        
        print(f"✅ Imported {count:,} products to ClickHouse")
    except Exception as e:
        print(f"⚠️  ClickHouse write skipped: {e}")
    
    return count


def main():
    if len(sys.argv) < 2:
        print("Usage: spark-submit import_products_spark.py <excel_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        sys.exit(1)
    
    # Initialize Spark Session with optimized configs
    spark = SparkSession.builder \
        .appName("ImportProducts-Spark") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.sql.adaptive.skewJoin.enabled", "true") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    print("=" * 70)
    print("🔥 PYSPARK ETL: Import Products")
    print("=" * 70)
    
    try:
        count = import_products(spark, file_path)
        
        print("\n" + "=" * 70)
        print(f"✅ SUCCESS: Imported {count:,} products using Spark")
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
