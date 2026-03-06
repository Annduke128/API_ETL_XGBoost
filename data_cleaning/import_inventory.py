"""
Import file Excel tồn kho (Xuất/Nhập/Tồn) vào PostgreSQL
File format: BaoCaoXuatNhapTon_*.xlsx
Join với bảng products qua ma_vach (mã vạch)
"""

import pandas as pd
import sys
import os
import re
from datetime import datetime

sys.path.insert(0, '/app')
from db_connectors import PostgreSQLConnector


def parse_date_from_filename(filename):
    """Trích xuất ngày từ tên file, ví dụ: BaoCaoXuatNhapTon_KV06032026 -> 2026-03-06"""
    # Pattern: KV + DDMMYYYY
    match = re.search(r'KV(\d{2})(\d{2})(\d{4})', filename)
    if match:
        day, month, year = match.groups()
        try:
            return datetime(int(year), int(month), int(day)).date()
        except:
            pass
    return datetime.now().date()


def clean_numeric(value):
    """Làm sạch giá trị số, xử lý cả string có dấu phẩy"""
    if pd.isna(value):
        return 0
    if isinstance(value, (int, float)):
        return int(value) if value == int(value) else float(value)
    # Xử lý string
    value_str = str(value).replace(',', '').replace('"', '').strip()
    try:
        return float(value_str)
    except:
        return 0


def import_inventory(file_path):
    """Import file Excel tồn kho"""
    
    print(f"📖 Đọc file: {file_path}")
    filename = os.path.basename(file_path)
    
    # Parse ngày từ tên file
    ngay_bao_cao = parse_date_from_filename(filename)
    print(f"📅 Ngày báo cáo: {ngay_bao_cao}")
    
    # Đọc Excel
    df = pd.read_excel(file_path, sheet_name=0)
    print(f"📊 Tổng số dòng: {len(df)}")
    print(f"📋 Các cột: {list(df.columns)}")
    
    # Mapping cột từ tiếng Việt sang snake_case
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
    df = df.rename(columns=column_mapping)
    
    # Kiểm tra cột bắt buộc
    required_cols = ['ma_vach', 'chi_nhanh', 'ton_dau_ky', 'sl_nhap', 'sl_xuat', 'ton_cuoi_ky']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"❌ Thiếu cột: {missing_cols}")
        print(f"Các cột hiện có: {list(df.columns)}")
        return
    
    # Làm sạch dữ liệu
    print("🧹 Làm sạch dữ liệu...")
    
    # Xử lý numeric columns
    numeric_cols = ['ton_dau_ky', 'gia_tri_dau_ky', 'sl_nhap', 'gia_tri_nhap', 
                    'sl_xuat', 'gia_tri_xuat', 'ton_cuoi_ky', 'gia_tri_cuoi_ky']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_numeric)
    
    # Xử lý string columns
    string_cols = ['nhom_hang', 'ma_hang', 'ma_vach', 'ten_hang', 'thuong_hieu', 'don_vi_tinh', 'chi_nhanh']
    for col in string_cols:
        if col in df.columns:
            df[col] = df[col].fillna('').astype(str)
    
    # Thêm metadata
    df['ngay_bao_cao'] = ngay_bao_cao
    df['week_year'] = ngay_bao_cao.strftime('%Y-%W')
    df['source_file'] = filename
    
    # Loại bỏ dòng không có mã vạch
    initial_count = len(df)
    df = df[df['ma_vach'].str.strip() != '']
    print(f"✅ Sau khi loại bỏ dòng không có mã vạch: {len(df)}/{initial_count}")
    
    # Connect PostgreSQL
    pg = PostgreSQLConnector(
        host=os.getenv('POSTGRES_HOST', 'postgres'),
        database=os.getenv('POSTGRES_DB', 'retail_db'),
        user=os.getenv('POSTGRES_USER', 'retail_user'),
        password=os.getenv('POSTGRES_PASSWORD', 'retail_password')
    )
    
    # Kiểm tra products có tồn tại không
    print("🔍 Kiểm tra mapping với bảng products...")
    from sqlalchemy import text
    with pg.get_connection() as conn:
        # Lấy danh sách ma_vach từ products
        result = conn.execute(text("SELECT ma_vach FROM products WHERE ma_vach IS NOT NULL"))
        valid_barcodes = set([row[0] for row in result])
    
    df['co_trong_products'] = df['ma_vach'].isin(valid_barcodes)
    matched = df['co_trong_products'].sum()
    print(f"✅ Có {matched}/{len(df)} sản phẩm khớp với bảng products ({matched/len(df)*100:.1f}%)")
    
    if matched == 0:
        print("⚠️  Cảnh báo: Không có sản phẩm nào khớp! Kiểm tra lại mã vạch.")
        print("Danh sách mã vạch mẫu trong products:", list(valid_barcodes)[:5])
    
    # Chuẩn bị data để insert
    insert_cols = ['ngay_bao_cao', 'week_year', 'nhom_hang', 'ma_hang', 'ma_vach', 
                   'ten_hang', 'thuong_hieu', 'don_vi_tinh', 'chi_nhanh',
                   'ton_dau_ky', 'gia_tri_dau_ky', 'sl_nhap', 'gia_tri_nhap',
                   'sl_xuat', 'gia_tri_xuat', 'ton_cuoi_ky', 'gia_tri_cuoi_ky',
                   'source_file']
    
    # Chỉ lấy các cột có trong dataframe
    insert_cols = [col for col in insert_cols if col in df.columns]
    df_insert = df[insert_cols].copy()
    
    # Xóa dữ liệu cũ cùng ngày để tránh duplicate
    print(f"🗑️  Xóa dữ liệu cũ cùng ngày {ngay_bao_cao}...")
    with pg.get_connection() as conn:
        conn.execute(
            text("DELETE FROM inventory_transactions WHERE ngay_bao_cao = :ngay"),
            {'ngay': ngay_bao_cao}
        )
        conn.commit()
    
    # Insert dữ liệu mới
    print(f"💾 Insert {len(df_insert)} dòng vào inventory_transactions...")
    with pg.get_connection() as conn:
        df_insert.to_sql('inventory_transactions', conn, if_exists='append', index=False)
    
    # Hiển thị summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"✅ Đã import: {len(df_insert)} dòng")
    print(f"📅 Ngày báo cáo: {ngay_bao_cao}")
    print(f"🏪 Chi nhánh: {df['chi_nhanh'].nunique()} chi nhánh")
    print(f"📦 Sản phẩm: {df['ma_vach'].nunique()} mã vạch")
    print(f"🔗 Khớp với products: {matched}/{len(df)} ({matched/len(df)*100:.1f}%)")
    print(f"📥 Tổng nhập: {df['sl_nhap'].sum():,.0f}")
    print(f"📤 Tổng xuất: {df['sl_xuat'].sum():,.0f}")
    print(f"📊 Tồn cuối: {df['ton_cuoi_ky'].sum():,.0f}")
    print("="*60)
    
    # Hiển thị top 5 sản phẩm có tồn cao nhất
    print("\n🏆 Top 5 sản phẩm tồn cuối cao nhất:")
    top5 = df.nlargest(5, 'ton_cuoi_ky')[['ma_vach', 'ten_hang', 'chi_nhanh', 'ton_cuoi_ky']]
    for _, row in top5.iterrows():
        print(f"   - {row['ma_vach']} | {row['ten_hang'][:40]} | {row['chi_nhanh']} | {row['ton_cuoi_ky']:,.0f}")


if __name__ == '__main__':
    file_path = sys.argv[1] if len(sys.argv) > 1 else '/csv_input/BaoCaoXuatNhapTon_KV06032026-102339-079.xlsx'
    import_inventory(file_path)
