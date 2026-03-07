#!/usr/bin/env python3
"""
PySpark ETL: Import Sales from Excel to PostgreSQL (transactions + transaction_details)
Parallel processing with Spark
"""

import os
import sys
import re
import unicodedata
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, lit, current_timestamp, coalesce, trim, when,
    first, count, sum as spark_sum, row_number, monotonically_increasing_id
)
from pyspark.sql.window import Window
from pyspark.sql.types import *


def parse_date_from_filename(filename):
    """Extract date from filename like BaoCaoBanHang_KV06032026"""
    match = re.search(r'KV(\d{2})(\d{2})(\d{4})', filename)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"
    return datetime.now().strftime('%Y-%m-%d')


def clean_numeric(value):
    """Clean numeric value"""
    if value is None:
        return 0.0
    try:
        return float(str(value).replace(',', '').replace('"', '').strip())
    except:
        return 0.0


def normalize_unicode(s):
    """Normalize unicode string to NFC form"""
    return unicodedata.normalize('NFC', s)

def find_column(columns, pattern):
    """Find column name containing pattern (with unicode normalization)"""
    pattern_norm = normalize_unicode(pattern.lower())
    for c in columns:
        if pattern_norm in normalize_unicode(c.lower()):
            return c
    return None


def import_sales(spark, file_path):
    """Import sales using PySpark"""
    
    filename = os.path.basename(file_path)
    ngay_bao_cao = parse_date_from_filename(filename)
    
    print(f"🔥 [SPARK] Processing: {filename}")
    print(f"📅 Date: {ngay_bao_cao}")
    
    # Read Excel
    import pandas as pd
    from sqlalchemy import text, create_engine
    
    print("📖 Reading Excel file...")
    pandas_df = pd.read_excel(file_path, engine='openpyxl')
    total_rows = len(pandas_df)
    print(f"📊 Total rows: {total_rows:,}")
    
    # Find column names
    cols = list(pandas_df.columns)
    col_ma_gd = find_column(cols, 'Mã giao dịch')
    col_chi_nhanh = find_column(cols, 'Chi nhánh')
    # Ưu tiên cột 'Thởi gian (theo giao dịch)' có datetime đầy đủ
    col_thoi_gian = find_column(cols, 'giao dịch)')  # Tìm cột chứa 'giao dịch)' 
    if not col_thoi_gian:
        col_thoi_gian = find_column(cols, 'Thởi gian')
    col_tong_tien = find_column(cols, 'Tổng tiền hàng')
    col_giam_gia = find_column(cols, 'Giảm giá')
    col_doanh_thu = find_column(cols, 'Doanh thu')
    col_gia_von = find_column(cols, 'Tổng giá vốn')
    col_loi_nhuan = find_column(cols, 'Lợi nhuận gộp')
    col_ma_hang = find_column(cols, 'Mã hàng')
    col_sl = find_column(cols, 'SL')
    col_gia_ban = find_column(cols, 'Giá bán')
    col_gia_von_sp = find_column(cols, 'Giá vốn')
    
    print(f"   Found columns: {col_ma_gd}, {col_chi_nhanh}")
    
    # Convert to Spark DataFrame
    df = spark.createDataFrame(pandas_df)
    
    # Group by transaction (parallel aggregation)
    print("🔄 Grouping transactions...")
    
    agg_exprs = [
        first(col_chi_nhanh).alias('chi_nhanh'),
        first(col_tong_tien).alias('tong_tien_hang'),
        first(col_giam_gia).alias('giam_gia'),
        first(col_doanh_thu).alias('doanh_thu'),
        first(col_gia_von).alias('tong_gia_von'),
        first(col_loi_nhuan).alias('loi_nhuan_gop')
    ]
    
    if col_thoi_gian:
        agg_exprs.append(first(col_thoi_gian).alias('thoi_gian_raw'))
    
    transactions = df.groupBy(col_ma_gd).agg(*agg_exprs)
    
    # Clean numeric columns
    from pyspark.sql.functions import udf
    clean_numeric_udf = udf(clean_numeric, DoubleType())
    
    numeric_cols = ['tong_tien_hang', 'giam_gia', 'doanh_thu', 'tong_gia_von', 'loi_nhuan_gop']
    for nc in numeric_cols:
        if nc in transactions.columns:
            transactions = transactions.withColumn(nc, clean_numeric_udf(col(nc)))
    
    tx_count = transactions.count()
    print(f"✅ {tx_count:,} unique transactions")
    
    # Write to PostgreSQL using pandas (for simplicity with RETURNING id)
    print("💾 Writing transactions to PostgreSQL...")
    
    pg_uri = f"postgresql://{os.getenv('POSTGRES_USER', 'retail_user')}:{os.getenv('POSTGRES_PASSWORD', 'retail_password')}@{os.getenv('POSTGRES_HOST', 'postgres')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'retail_db')}"
    engine = create_engine(pg_uri)
    
    # Delete old data
    with engine.connect() as conn:
        conn.execute(text("""
            DELETE FROM transaction_details 
            WHERE giao_dich_id IN (
                SELECT id FROM transactions WHERE DATE(thoi_gian) = :ngay
            )
        """), {"ngay": ngay_bao_cao})
        conn.execute(text("DELETE FROM transactions WHERE DATE(thoi_gian) = :ngay"), {"ngay": ngay_bao_cao})
        conn.commit()
    
    # Convert to pandas for detailed insert with product lookup
    tx_pd = transactions.toPandas()
    
    inserted_tx = 0
    inserted_details = 0
    
    with engine.connect() as conn:
        for idx, row in tx_pd.iterrows():
            # Parse datetime - hỗ trợ cả string và datetime object
            thoi_gian_val = row.get('thoi_gian_raw', None) if 'thoi_gian_raw' in row else None
            
            if pd.notna(thoi_gian_val):
                # Nếu là string, parse nó
                if isinstance(thoi_gian_val, str):
                    try:
                        thoi_gian = pd.to_datetime(thoi_gian_val, dayfirst=True)
                    except:
                        thoi_gian = datetime.combine(datetime.strptime(ngay_bao_cao, '%Y-%m-%d'), datetime.min.time())
                # Nếu đã là datetime, dùng luôn
                elif isinstance(thoi_gian_val, (datetime, pd.Timestamp)):
                    thoi_gian = thoi_gian_val
                else:
                    thoi_gian = datetime.combine(datetime.strptime(ngay_bao_cao, '%Y-%m-%d'), datetime.min.time())
            else:
                # Fallback về ngày từ filename nếu không có thởi gian
                thoi_gian = datetime.combine(datetime.strptime(ngay_bao_cao, '%Y-%m-%d'), datetime.min.time())
            
            # Insert transaction
            result = conn.execute(text("""
                INSERT INTO transactions (ma_giao_dich, thoi_gian, tong_tien_hang, giam_gia, doanh_thu, tong_gia_von, loi_nhuan_gop)
                VALUES (:ma_gd, :thoi_gian, :tong_tien, :giam_gia, :doanh_thu, :gia_von, :loi_nhuan)
                ON CONFLICT (ma_giao_dich, thoi_gian) DO UPDATE SET
                    tong_tien_hang = EXCLUDED.tong_tien_hang,
                    giam_gia = EXCLUDED.giam_gia,
                    doanh_thu = EXCLUDED.doanh_thu
                RETURNING id
            """), {
                "ma_gd": str(row[col_ma_gd]),
                "thoi_gian": thoi_gian,
                "tong_tien": clean_numeric(row['tong_tien_hang']),
                "giam_gia": clean_numeric(row['giam_gia']),
                "doanh_thu": clean_numeric(row['doanh_thu']),
                "gia_von": clean_numeric(row['tong_gia_von']),
                "loi_nhuan": clean_numeric(row['loi_nhuan_gop'])
            })
            
            giao_dich_id = result.fetchone()[0]
            inserted_tx += 1
            
            # Insert details for this transaction
            details = pandas_df[pandas_df[col_ma_gd] == row[col_ma_gd]]
            
            for _, detail_row in details.iterrows():
                ma_hang = str(detail_row.get(col_ma_hang, '')) if col_ma_hang else ''
                ma_vach = str(detail_row.get('Mã vạch', '')) if 'Mã vạch' in detail_row else ''
                
                # Lookup product_id
                product_id = None
                if ma_hang or ma_vach:
                    product_result = conn.execute(text("""
                        SELECT id FROM products WHERE ma_hang = :ma_hang OR ma_vach = :ma_vach LIMIT 1
                    """), {"ma_hang": ma_hang, "ma_vach": ma_vach})
                    product_row = product_result.fetchone()
                    product_id = product_row[0] if product_row else None
                
                if product_id:
                    conn.execute(text("""
                        INSERT INTO transaction_details (giao_dich_id, product_id, so_luong, gia_ban, gia_von)
                        VALUES (:giao_dich_id, :product_id, :so_luong, :gia_ban, :gia_von)
                    """), {
                        "giao_dich_id": giao_dich_id,
                        "product_id": product_id,
                        "so_luong": int(clean_numeric(detail_row.get(col_sl, 0))),
                        "gia_ban": clean_numeric(detail_row.get(col_gia_ban, 0)),
                        "gia_von": clean_numeric(detail_row.get(col_gia_von_sp, 0))
                    })
                    inserted_details += 1
        
        conn.commit()
    
    print(f"✅ Imported {inserted_tx} transactions, {inserted_details} details")
    
    return inserted_tx, inserted_details


def main():
    if len(sys.argv) < 2:
        print("Usage: spark-submit import_sales_spark.py <excel_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        sys.exit(1)
    
    spark = SparkSession.builder \
        .appName("ImportSales-Spark") \
        .config("spark.sql.adaptive.enabled", "true") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    print("=" * 70)
    print("🔥 PYSPARK ETL: Import Sales")
    print("=" * 70)
    
    try:
        tx_count, details_count = import_sales(spark, file_path)
        
        print("\n" + "=" * 70)
        print(f"✅ SUCCESS: {tx_count} transactions, {details_count} details using Spark")
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
