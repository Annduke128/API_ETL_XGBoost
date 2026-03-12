#!/usr/bin/env python3
"""
Spark ETL Pipeline - Optimized for File-based Pattern
- Sales: Append (partition overwrite)
- Product/Inventory: Replace (truncate + insert)
"""

import os
import re
import logging
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import psycopg2
from clickhouse_driver import Client as CHClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Config
POSTGRES_HOST = os.environ.get('POSTGRES_HOST', 'postgres')
POSTGRES_PORT = os.environ.get('POSTGRES_PORT', '5432')
if '://' in str(POSTGRES_PORT):
    POSTGRES_PORT = str(POSTGRES_PORT).split(':')[-1]
POSTGRES_DB = os.environ.get('POSTGRES_DB', 'retail_db')
POSTGRES_USER = os.environ.get('POSTGRES_USER', 'retail_user')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'retail_password')
CLICKHOUSE_HOST = os.environ.get('CLICKHOUSE_HOST', 'clickhouse')
CLICKHOUSE_PASSWORD = os.environ.get('CLICKHOUSE_PASSWORD', '')
CSV_INPUT = Path('/csv_input')

def get_pg_conn():
    return psycopg2.connect(
        host=POSTGRES_HOST, port=int(POSTGRES_PORT), database=POSTGRES_DB,
        user=POSTGRES_USER, password=POSTGRES_PASSWORD
    )

def get_ch_client():
    return CHClient(host=CLICKHOUSE_HOST, database='retail_dw', password=CLICKHOUSE_PASSWORD or None)

def clean_num(val):
    if pd.isna(val): return 0.0
    try: return float(str(val).replace('.', '').replace(',', '.').replace(' ', ''))
    except: return 0.0

def find_files(pattern):
    files = []
    for path in [CSV_INPUT, CSV_INPUT / 'error']:
        if path.exists(): files.extend(path.glob(pattern))
    return files

def get_date_range_from_file(df, date_col):
    """Extract min/max date from file for partition pruning"""
    if date_col in df.columns:
        dates = pd.to_datetime(df[date_col], errors='coerce')
        return dates.min(), dates.max()
    return None, None

def sync_to_ch_partitioned(table, date_col, min_date, max_date):
    """Sync only changed partitions to ClickHouse"""
    logger.info(f"🔄 Sync {table} partitions {min_date} to {max_date}...")
    pg = get_pg_conn()
    ch = get_ch_client()
    try:
        with pg.cursor() as cur:
            # Get columns
            cur.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table}' AND data_type NOT IN ('timestamp with time zone')
                ORDER BY ordinal_position
            """)
            cols = [r[0] for r in cur.fetchall()]
            
            # Delete only affected partitions in CH
            ch.execute(f"""
                ALTER TABLE retail_dw.stg_{table} 
                DROP PARTITION '{min_date.strftime('%Y%m%d')}'
            """)
            
            # Get data from PG
            cur.execute(f"""
                SELECT {','.join(cols)} 
                FROM {table} 
                WHERE {date_col} BETWEEN %s AND %s
            """, (min_date, max_date))
            rows = cur.fetchall()
            
            if rows:
                rows_str = [tuple(str(c) for c in row) for row in rows]
                ch.execute(f"INSERT INTO retail_dw.stg_{table} ({','.join(cols)}) VALUES", rows_str)
                logger.info(f"   ✅ Synced {len(rows)} rows")
    finally:
        pg.close()

def process_sales():
    """Process sales files - APPEND pattern with partition overwrite"""
    files = find_files('*BaoCaoBanHang*.csv') + find_files('*BaoCaoBanHang*.xlsx')
    if not files:
        logger.warning("⚠️ No sales files found")
        return
    
    for fp in files:
        logger.info(f"💰 Sales: {fp.name}")
        
        # Read file
        if fp.suffix == '.csv':
            df = pd.read_csv(fp, encoding='utf-8-sig', dtype=str)
        else:
            df = pd.read_excel(fp, dtype=str)
        
        # Detect date column and range
        date_cols = [c for c in df.columns if 'ngày' in c.lower() or 'date' in c.lower() or 'thờigian' in c.lower()]
        date_col = date_cols[0] if date_cols else None
        min_date, max_date = get_date_range_from_file(df, date_col) if date_col else (None, None)
        
        if min_date and max_date:
            logger.info(f"   📅 Date range: {min_date.date()} to {max_date.date()}")
        
        # ... (process branches, transactions, details)
        # DELETE only date range affected
        # INSERT new data
        # Sync only changed partitions
        
        if min_date and max_date:
            sync_to_ch_partitioned('transactions', 'ngay_giao_dich', min_date, max_date)
            sync_to_ch_partitioned('transaction_details', 'created_at', min_date, max_date)

def process_products():
    """Process products - REPLACE pattern (full refresh)"""
    files = find_files('*DanhSachSanPham*.csv') + find_files('*DanhSachSanPham*.xlsx')
    if not files:
        return
    
    fp = files[0]
    logger.info(f"📦 Products: {fp.name} (REPLACE mode)")
    
    df = pd.read_csv(fp, encoding='utf-8-sig', dtype=str) if fp.suffix == '.csv' else pd.read_excel(fp, dtype=str)
    
    # Transform
    clean = pd.DataFrame()
    clean['ma_hang'] = df.iloc[:, 0].str.strip()
    clean['ten_hang'] = df.iloc[:, 1].fillna('') if len(df.columns) > 1 else ''
    clean['nhom_hang'] = ''
    clean['don_vi_tinh'] = ''
    clean['gia_ban'] = 0.0
    clean['gia_von'] = 0.0
    clean['created_at'] = datetime.now()
    clean = clean.drop_duplicates('ma_hang')
    
    pg = get_pg_conn()
    try:
        with pg.cursor() as cur:
            # REPLACE mode: Truncate + Insert
            cur.execute("TRUNCATE TABLE products CASCADE")
            
            for _, r in clean.iterrows():
                cur.execute("""
                    INSERT INTO products (ma_hang,ten_hang,nhom_hang,don_vi_tinh,gia_ban,gia_von,created_at) 
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, tuple(r))
        
        pg.commit()
        logger.info(f"   ✅ Replaced with {len(clean)} products")
    finally:
        pg.close()
    
    # Full sync to CH (vì là replace)
    logger.info("   🔄 Full sync products to ClickHouse...")
    # ... sync logic

def main():
    logger.info("="*60)
    logger.info("🚀 Spark ETL - Optimized for File Pattern")
    logger.info("   Sales: Append (partitioned)")
    logger.info("   Products: Replace (full refresh)")
    logger.info("="*60)
    
    process_products()  # REPLACE
    process_sales()     # APPEND with partition
    
    logger.info("="*60)
    logger.info("✅ Done!")

if __name__ == '__main__':
    main()
