#!/usr/bin/env python3
"""Spark ETL Pipeline v23 - Auto-add missing products"""
import os
import re
import logging
from datetime import datetime
from pathlib import Path
import pandas as pd
import psycopg2
from clickhouse_driver import Client as CHClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

POSTGRES_HOST = os.environ.get('POSTGRES_HOST', 'postgres')
POSTGRES_PORT = os.environ.get('POSTGRES_PORT', '5432')
if '://' in str(POSTGRES_PORT): POSTGRES_PORT = str(POSTGRES_PORT).split(':')[-1]
POSTGRES_DB = os.environ.get('POSTGRES_DB', 'retail_db')
POSTGRES_USER = os.environ.get('POSTGRES_USER', 'retail_user')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'retail_password')
CLICKHOUSE_HOST = os.environ.get('CLICKHOUSE_HOST', 'clickhouse')
CLICKHOUSE_PASSWORD = os.environ.get('CLICKHOUSE_PASSWORD', '')
CSV_INPUT = Path('/csv_input')

def get_pg_conn():
    return psycopg2.connect(host=POSTGRES_HOST, port=int(POSTGRES_PORT), database=POSTGRES_DB,
                            user=POSTGRES_USER, password=POSTGRES_PASSWORD)

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

def parse_date(fn):
    m = re.search(r'KV(\d{2})(\d{2})(\d{4})', fn)
    if m: return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return datetime.now().strftime('%Y-%m-%d')

def sync_to_ch(table, cols=None):
    logger.info(f"🔄 Sync {table}...")
    pg = get_pg_conn()
    ch = get_ch_client()
    try:
        with pg.cursor() as cur:
            if cols is None:
                cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table}' AND data_type NOT IN ('timestamp with time zone') ORDER BY ordinal_position")
                cols = [r[0] for r in cur.fetchall()]
            ch.execute(f"TRUNCATE TABLE retail_dw.stg_{table}")
            cur.execute(f"SELECT {','.join(cols)} FROM {table}")
            rows = cur.fetchall()
            if rows:
                rows_str = [tuple(str(c) for c in row) for row in rows]
                ch.execute(f"INSERT INTO retail_dw.stg_{table} ({','.join(cols)}) VALUES", rows_str)
                logger.info(f"   ✅ {len(rows)} rows")
    finally:
        pg.close()

def process_products():
    files = find_files('*DanhSachSanPham*.csv') + find_files('*DanhSachSanPham*.xlsx')
    if not files: return
    fp = files[0]
    logger.info(f"📦 Products: {fp.name}")
    df = pd.read_csv(fp, encoding='utf-8-sig', dtype=str) if fp.suffix=='.csv' else pd.read_excel(fp, dtype=str)
    
    c_ma = next((c for c in df.columns if 'mã' in c.lower() and 'hàng' in c.lower()), df.columns[0])
    c_ten = next((c for c in df.columns if 'tên' in c.lower() and 'hàng' in c.lower()), None)
    c_nhom = next((c for c in df.columns if 'nhóm' in c.lower()), None)
    c_dvt = next((c for c in df.columns if 'đơn vị' in c.lower()), None)
    c_giaban = next((c for c in df.columns if 'giá bán' in c.lower()), None)
    c_giavon = next((c for c in df.columns if 'giá vốn' in c.lower()), None)
    
    clean = pd.DataFrame()
    clean['ma_hang'] = df[c_ma].str.strip()
    clean['ten_hang'] = df[c_ten].fillna('') if c_ten else ''
    clean['nhom_hang'] = df[c_nhom].fillna('') if c_nhom else ''
    clean['don_vi_tinh'] = df[c_dvt].fillna('') if c_dvt else ''
    clean['gia_ban'] = (df[c_giaban].fillna('0') if c_giaban else pd.Series(['0']*len(df))).apply(clean_num)
    clean['gia_von'] = (df[c_giavon].fillna('0') if c_giavon else pd.Series(['0']*len(df))).apply(clean_num)
    clean['created_at'] = datetime.now()
    clean = clean.drop_duplicates('ma_hang')
    
    pg = get_pg_conn()
    try:
        with pg.cursor() as cur:
            cur.execute("TRUNCATE TABLE products CASCADE")
            for _,r in clean.iterrows():
                cur.execute("INSERT INTO products (ma_hang,ten_hang,nhom_hang,don_vi_tinh,gia_ban,gia_von,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                            (r.ma_hang, r.ten_hang, r.nhom_hang, r.don_vi_tinh, r.gia_ban, r.gia_von, r.created_at))
        pg.commit()
        logger.info(f"   ✅ {len(clean)} products")
    finally:
        pg.close()
    sync_to_ch('products')

def add_missing_products(all_ma_hang):
    """Add products that exist in sales but not in products table"""
    pg = get_pg_conn()
    added = 0
    try:
        with pg.cursor() as cur:
            for ma_hang in all_ma_hang:
                cur.execute("INSERT INTO products (ma_hang, ten_hang, nhom_hang, don_vi_tinh, gia_ban, gia_von, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                            (ma_hang, f'Product {ma_hang}', '', '', 0.0, 0.0, datetime.now()))
                if cur.rowcount > 0:
                    added += 1
        pg.commit()
        if added > 0:
            logger.info(f"   ✅ Added {added} missing products")
    finally:
        pg.close()

def process_sales():
    files = find_files('*BaoCaoBanHang*.csv') + find_files('*BaoCaoBanHang*.xlsx')
    if not files: return
    
    for fp in files:
        logger.info(f"💰 Sales: {fp.name}")
        ngay = parse_date(fp.name)
        df = pd.read_csv(fp, encoding='utf-8-sig', dtype=str) if fp.suffix=='.csv' else pd.read_excel(fp, dtype=str)
        
        c_ma_gd = next((c for c in df.columns if 'mã' in c.lower() and 'giao dịch' in c.lower()), None)
        c_cn = next((c for c in df.columns if 'chi nhánh' in c.lower()), None)
        c_ma_h = next((c for c in df.columns if 'mã' in c.lower() and 'hàng' in c.lower()), None)
        c_ten_h = next((c for c in df.columns if 'tên' in c.lower() and 'hàng' in c.lower()), None)
        c_sl = next((c for c in df.columns if 'số lượng' in c.lower()), None)
        c_dg = next((c for c in df.columns if 'đơn giá' in c.lower()), None)
        c_tt = next((c for c in df.columns if 'thành tiền' in c.lower()), None)
        c_tong = next((c for c in df.columns if 'tổng' in c.lower()), None)
        
        if not c_ma_gd or not c_ma_h:
            logger.warning("   ⚠️ Skip - missing columns")
            continue
        
        pg = get_pg_conn()
        try:
            # Branches
            if c_cn:
                branches = df[c_cn].dropna().unique()
                with pg.cursor() as cur:
                    for b in branches:
                        cur.execute("INSERT INTO branches (ma_chi_nhanh,ten_chi_nhanh,dia_chi,created_at) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                                    (b.strip(), b.strip(), '', datetime.now()))
                pg.commit()
                logger.info(f"   ✅ {len(branches)} branches")
            
            # Delete old data
            with pg.cursor() as cur:
                cur.execute("DELETE FROM transaction_details WHERE ma_giao_dich IN (SELECT ma_giao_dich FROM transactions WHERE ngay_giao_dich=%s)", (ngay,))
                cur.execute("DELETE FROM transactions WHERE ngay_giao_dich=%s", (ngay,))
            pg.commit()
            
            # Transactions
            trans = pd.DataFrame()
            trans['ma_giao_dich'] = df[c_ma_gd].str.strip()
            trans['ma_chi_nhanh'] = df[c_cn].fillna('Unknown').str.strip() if c_cn else 'Unknown'
            trans['ngay_giao_dich'] = ngay
            trans['tong_tien'] = (df[c_tong].fillna('0') if c_tong else (df[c_tt].fillna('0') if c_tt else pd.Series(['0']*len(df)))).apply(clean_num)
            trans['phuong_thuc_thanh_toan'] = ''
            trans['created_at'] = datetime.now()
            
            trans_agg = trans.groupby('ma_giao_dich').agg({
                'ma_chi_nhanh':'first', 'ngay_giao_dich':'first', 'tong_tien':'sum',
                'phuong_thuc_thanh_toan':'first', 'created_at':'first'
            }).reset_index()
            
            with pg.cursor() as cur:
                for _,r in trans_agg.iterrows():
                    cur.execute("INSERT INTO transactions (ma_giao_dich,ma_chi_nhanh,ngay_giao_dich,tong_tien,phuong_thuc_thanh_toan,created_at) VALUES (%s,%s,%s,%s,%s,%s)",
                                (r.ma_giao_dich, r.ma_chi_nhanh, r.ngay_giao_dich, r.tong_tien, r.phuong_thuc_thanh_toan, r.created_at))
            pg.commit()
            logger.info(f"   ✅ {len(trans_agg)} transactions")
            
            # Add missing products before inserting details
            all_ma_hang = df[c_ma_h].dropna().str.strip().unique()
            add_missing_products(all_ma_hang)
            
            # Transaction Details
            det = pd.DataFrame()
            det['ma_giao_dich'] = df[c_ma_gd].str.strip()
            det['ma_hang'] = df[c_ma_h].str.strip()
            det['so_luong'] = (df[c_sl].fillna('1') if c_sl else pd.Series(['1']*len(df))).apply(lambda x: int(clean_num(x)) if clean_num(x)>0 else 1)
            det['don_gia'] = (df[c_dg].fillna('0') if c_dg else pd.Series(['0']*len(df))).apply(clean_num)
            det['thanh_tien'] = (df[c_tt].fillna('0') if c_tt else pd.Series(['0']*len(df))).apply(clean_num)
            det['created_at'] = datetime.now()
            
            det_agg = det.groupby(['ma_giao_dich','ma_hang']).agg({
                'so_luong':'sum', 'don_gia':'mean', 'thanh_tien':'sum', 'created_at':'first'
            }).reset_index()
            
            with pg.cursor() as cur:
                for _,r in det_agg.iterrows():
                    cur.execute("INSERT INTO transaction_details (ma_giao_dich,ma_hang,so_luong,don_gia,thanh_tien,created_at) VALUES (%s,%s,%s,%s,%s,%s)",
                                (r.ma_giao_dich, r.ma_hang, r.so_luong, r.don_gia, r.thanh_tien, r.created_at))
            pg.commit()
            logger.info(f"   ✅ {len(det_agg)} details")
            
            sync_to_ch('transactions', ['ma_giao_dich','ma_chi_nhanh','ngay_giao_dich','tong_tien','phuong_thuc_thanh_toan'])
            sync_to_ch('transaction_details', ['ma_giao_dich','ma_hang','so_luong','don_gia','thanh_tien'])
        finally:
            pg.close()

def main():
    logger.info("="*60)
    logger.info("🚀 Spark ETL Pipeline v23")
    logger.info("="*60)
    process_products()
    process_sales()
    logger.info("="*60)
    logger.info("✅ Done!")

if __name__=='__main__':
    main()
