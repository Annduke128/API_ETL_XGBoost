#!/usr/bin/env python3
"""
Spark ETL Pipeline - Full Load
Import CSV/Excel to PostgreSQL + Sync to ClickHouse
v15: Fix fillna error
"""

import os
import re
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import psycopg2
from clickhouse_driver import Client as CHClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment
POSTGRES_HOST = os.environ.get('POSTGRES_HOST', 'postgres')
POSTGRES_PORT = os.environ.get('POSTGRES_PORT', '5432')
POSTGRES_DB = os.environ.get('POSTGRES_DB', 'retail_db')
POSTGRES_USER = os.environ.get('POSTGRES_USER', 'retail_user')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'retail_password')
CLICKHOUSE_HOST = os.environ.get('CLICKHOUSE_HOST', 'clickhouse')

CSV_INPUT = Path('/csv_input')


def find_files(pattern):
    """Find files matching pattern"""
    files = []
    for path in [CSV_INPUT, CSV_INPUT / 'error']:
        if path.exists():
            files.extend(path.glob(pattern))
    return files


def parse_date_from_filename(filename):
    """Parse date from filename like KV15022026 -> 2026-02-15"""
    match = re.search(r'KV(\d{2})(\d{2})(\d{4})', filename)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"
    return datetime.now().strftime('%Y-%m-%d')


def clean_numeric(val):
    """Clean numeric value from Vietnamese format"""
    if pd.isna(val):
        return 0.0
    s = str(val).replace('.', '').replace(',', '.').replace(' ', '')
    try:
        return float(s)
    except:
        return 0.0


def get_postgres_conn():
    """Get PostgreSQL connection"""
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )


def get_ch_client():
    """Get ClickHouse client"""
    return CHClient(host=CLICKHOUSE_HOST, database='retail_dw')


def sync_table_to_clickhouse(table_name, pg_table=None, columns=None):
    """Sync PostgreSQL table to ClickHouse"""
    pg_table = pg_table or table_name
    logger.info(f"🔄 Syncing {pg_table} to ClickHouse stg_{table_name}...")
    
    conn = get_postgres_conn()
    ch = get_ch_client()
    
    try:
        with conn.cursor() as cur:
            if columns is None:
                cur.execute(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = '{pg_table}' AND data_type NOT IN ('timestamp with time zone')
                    ORDER BY ordinal_position
                """)
                columns = [row[0] for row in cur.fetchall()]
            
            col_str = ', '.join(f'"{c}"' for c in columns)
            ch.execute(f"TRUNCATE TABLE retail_dw.stg_{table_name}")
            cur.execute(f"SELECT {col_str} FROM {pg_table}")
            rows = cur.fetchall()
            
            if rows:
                ch.execute(f"INSERT INTO retail_dw.stg_{table_name} ({col_str}) VALUES", rows)
                logger.info(f"   ✅ Synced {len(rows)} rows")
            else:
                logger.info(f"   ℹ️ No data to sync")
    finally:
        conn.close()


def process_products():
    """Process products CSV"""
    files = find_files('*DanhSachSanPham*.csv') + find_files('*DanhSachSanPham*.xlsx')
    if not files:
        logger.warning("⚠️ No products file found")
        return
    
    file_path = files[0]
    logger.info(f"📦 Processing products: {file_path.name}")
    
    if file_path.suffix == '.csv':
        df = pd.read_csv(file_path, encoding='utf-8-sig', dtype=str)
    else:
        df = pd.read_excel(file_path, dtype=str)
    
    # Column mapping
    col_map = {}
    for col in df.columns:
        if 'mã' in col.lower() and 'hàng' in col.lower():
            col_map['ma_hang'] = col
        elif 'tên' in col.lower() and 'hàng' in col.lower():
            col_map['ten_hang'] = col
        elif 'nhóm' in col.lower():
            col_map['nhom_hang'] = col
        elif 'đơn vị' in col.lower():
            col_map['don_vi_tinh'] = col
        elif 'giá bán' in col.lower():
            col_map['gia_ban'] = col
        elif 'giá vốn' in col.lower():
            col_map['gia_von'] = col
    
    # Transform
    df_clean = pd.DataFrame()
    df_clean['ma_hang'] = df[col_map.get('ma_hang', df.columns[0])].str.strip()
    df_clean['ten_hang'] = df[col_map.get('ten_hang', df.columns[0]) if col_map.get('ten_hang') else df.columns[0]].fillna('')
    df_clean['nhom_hang'] = df[col_map.get('nhom_hang', df.columns[0]) if col_map.get('nhom_hang') else df.columns[0]].fillna('') if col_map.get('nhom_hang') else ''
    df_clean['don_vi_tinh'] = df[col_map.get('don_vi_tinh', df.columns[0]) if col_map.get('don_vi_tinh') else df.columns[0]].fillna('') if col_map.get('don_vi_tinh') else ''
    df_clean['gia_ban'] = df[col_map.get('gia_ban', df.columns[0]) if col_map.get('gia_ban') else df.columns[0]].fillna('0').apply(clean_numeric) if col_map.get('gia_ban') else 0.0
    df_clean['gia_von'] = df[col_map.get('gia_von', df.columns[0]) if col_map.get('gia_von') else df.columns[0]].fillna('0').apply(clean_numeric) if col_map.get('gia_von') else 0.0
    df_clean['created_at'] = datetime.now()
    
    df_clean = df_clean.drop_duplicates(subset=['ma_hang'])
    
    conn = get_postgres_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE products CASCADE")
            
            for _, row in df_clean.iterrows():
                cur.execute("""
                    INSERT INTO products (ma_hang, ten_hang, nhom_hang, don_vi_tinh, gia_ban, gia_von, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, tuple(row))
        conn.commit()
        logger.info(f"   ✅ Inserted {len(df_clean)} products")
    finally:
        conn.close()
    
    sync_table_to_clickhouse('products')


def process_sales():
    """Process sales CSV files"""
    files = find_files('*BaoCaoBanHang*.csv') + find_files('*BaoCaoBanHang*.xlsx')
    if not files:
        logger.warning("⚠️ No sales files found")
        return
    
    for file_path in files:
        logger.info(f"💰 Processing sales: {file_path.name}")
        
        ngay_bao_cao = parse_date_from_filename(file_path.name)
        
        if file_path.suffix == '.csv':
            df = pd.read_csv(file_path, encoding='utf-8-sig', dtype=str)
        else:
            df = pd.read_excel(file_path, dtype=str)
        
        col_ma_gd = next((c for c in df.columns if 'mã' in c.lower() and 'giao dịch' in c.lower()), None)
        col_chi_nhanh = next((c for c in df.columns if 'chi nhánh' in c.lower()), None)
        col_ma_hang = next((c for c in df.columns if 'mã' in c.lower() and 'hàng' in c.lower()), None)
        col_so_luong = next((c for c in df.columns if 'số lượng' in c.lower()), None)
        col_don_gia = next((c for c in df.columns if 'đơn giá' in c.lower()), None)
        col_thanh_tien = next((c for c in df.columns if 'thành tiền' in c.lower()), None)
        col_tong_tien = next((c for c in df.columns if 'tổng' in c.lower() or 'tổng tiền' in c.lower()), None)
        
        if not col_ma_gd or not col_ma_hang:
            logger.warning(f"   ⚠️ Required columns not found, skipping")
            continue
        
        conn = get_postgres_conn()
        try:
            # Insert branches
            if col_chi_nhanh:
                branches = df[col_chi_nhanh].dropna().unique()
                with conn.cursor() as cur:
                    for branch in branches:
                        branch_clean = branch.strip() if branch else 'Unknown'
                        cur.execute("""
                            INSERT INTO branches (ma_chi_nhanh, ten_chi_nhanh, dia_chi, created_at)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (ma_chi_nhanh) DO NOTHING
                        """, (branch_clean, branch_clean, '', datetime.now()))
                conn.commit()
                logger.info(f"   ✅ Ensured {len(branches)} branches")
            
            # Delete old data
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM transaction_details WHERE ma_giao_dich IN (
                        SELECT ma_giao_dich FROM transactions WHERE ngay_giao_dich = %s
                    )
                """, (ngay_bao_cao,))
                cur.execute("DELETE FROM transactions WHERE ngay_giao_dich = %s", (ngay_bao_cao,))
            conn.commit()
            logger.info(f"   ✅ Deleted old data")
            
            # Build transactions
            trans_df = pd.DataFrame()
            trans_df['ma_giao_dich'] = df[col_ma_gd].str.strip()
            trans_df['ma_chi_nhanh'] = df[col_chi_nhanh].fillna('Unknown').str.strip() if col_chi_nhanh else 'Unknown'
            trans_df['ngay_giao_dich'] = ngay_bao_cao
            trans_df['tong_tien'] = df[col_tong_tien if col_tong_tien else col_thanh_tien].fillna('0').apply(clean_numeric) if (col_tong_tien or col_thanh_tien) else 0.0
            trans_df['phuong_thuc_thanh_toan'] = ''
            trans_df['created_at'] = datetime.now()
            
            trans_agg = trans_df.groupby('ma_giao_dich').agg({
                'ma_chi_nhanh': 'first',
                'ngay_giao_dich': 'first',
                'tong_tien': 'sum',
                'phuong_thuc_thanh_toan': 'first',
                'created_at': 'first'
            }).reset_index()
            
            with conn.cursor() as cur:
                for _, row in trans_agg.iterrows():
                    cur.execute("""
                        INSERT INTO transactions (ma_giao_dich, ma_chi_nhanh, ngay_giao_dich, tong_tien, phuong_thuc_thanh_toan, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, tuple(row))
            conn.commit()
            logger.info(f"   ✅ Inserted {len(trans_agg)} transactions")
            
            # Build details
            details_df = pd.DataFrame()
            details_df['ma_giao_dich'] = df[col_ma_gd].str.strip()
            details_df['ma_hang'] = df[col_ma_hang].str.strip()
            details_df['so_luong'] = df[col_so_luong].fillna('1').apply(lambda x: int(clean_numeric(x)) if clean_numeric(x) > 0 else 1) if col_so_luong else 1
            details_df['don_gia'] = df[col_don_gia].fillna('0').apply(clean_numeric) if col_don_gia else 0.0
            details_df['thanh_tien'] = df[col_thanh_tien].fillna('0').apply(clean_numeric) if col_thanh_tien else 0.0
            details_df['created_at'] = datetime.now()
            
            details_agg = details_df.groupby(['ma_giao_dich', 'ma_hang']).agg({
                'so_luong': 'sum',
                'don_gia': 'mean',
                'thanh_tien': 'sum',
                'created_at': 'first'
            }).reset_index()
            
            with conn.cursor() as cur:
                for _, row in details_agg.iterrows():
                    cur.execute("""
                        INSERT INTO transaction_details (ma_giao_dich, ma_hang, so_luong, don_gia, thanh_tien, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, tuple(row))
            conn.commit()
            logger.info(f"   ✅ Inserted {len(details_agg)} details")
            
            # Sync
            sync_table_to_clickhouse('transactions', columns=['ma_giao_dich', 'ma_chi_nhanh', 'ngay_giao_dich', 'tong_tien', 'phuong_thuc_thanh_toan'])
            sync_table_to_clickhouse('transaction_details', pg_table='transaction_details', 
                                    columns=['ma_giao_dich', 'ma_hang', 'so_luong', 'don_gia', 'thanh_tien'])
        finally:
            conn.close()


def main():
    logger.info("="*60)
    logger.info("🚀 Spark ETL Pipeline v15")
    logger.info("="*60)
    
    process_products()
    process_sales()
    
    logger.info("="*60)
    logger.info("✅ ETL Complete!")
    logger.info("="*60)


if __name__ == '__main__':
    main()
