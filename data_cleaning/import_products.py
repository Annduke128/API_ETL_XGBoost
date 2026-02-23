"""
Import DanhSachSanPham.csv vào PostgreSQL (bảng products)
File này chỉ chứa thông tin sản phẩm, không phải giao dịch
"""

import pandas as pd
import sys
import os

sys.path.insert(0, '/app')
from db_connectors import PostgreSQLConnector


def parse_nhom_hang(nhom_hang_str):
    """Parse 'Nhóm hàng(3 Cấp)' thành 3 cấp"""
    if pd.isna(nhom_hang_str):
        return '', '', ''
    
    parts = str(nhom_hang_str).split('>>')
    cap1 = parts[0].strip() if len(parts) > 0 else ''
    cap2 = parts[1].strip() if len(parts) > 1 else ''
    cap3 = parts[2].strip() if len(parts) > 2 else ''
    
    return cap1, cap2, cap3


def clean_numeric(value):
    """Làm sạch giá trị số"""
    if pd.isna(value):
        return 0.0
    
    value_str = str(value).replace(',', '').replace('"', '').strip()
    try:
        return float(value_str)
    except:
        return 0.0


def import_products(file_path):
    """Import file DanhSachSanPham.csv"""
    
    print(f"📖 Đọc file: {file_path}")
    df = pd.read_csv(file_path, encoding='utf-8-sig')
    print(f"📊 Tổng số sản phẩm: {len(df)}")
    
    # Parse nhóm hàng
    nhom_hang_parsed = df['Nhóm hàng(3 Cấp)'].apply(parse_nhom_hang)
    df['nhom_hang_cap_1'] = [x[0] for x in nhom_hang_parsed]
    df['nhom_hang_cap_2'] = [x[1] for x in nhom_hang_parsed]
    df['nhom_hang_cap_3'] = [x[2] for x in nhom_hang_parsed]
    
    # Mapping cột
    products_df = pd.DataFrame({
        'ma_hang': df['Mã hàng'].astype(str),
        'ma_vach': df['Mã vạch'].fillna('').astype(str),
        'ten_hang': df['Tên hàng'].astype(str),
        'thuong_hieu': df['Thương hiệu'].fillna('').astype(str),
        'nhom_hang_cap_1': df['nhom_hang_cap_1'],
        'nhom_hang_cap_2': df['nhom_hang_cap_2'],
        'nhom_hang_cap_3': df['nhom_hang_cap_3'],
        'gia_von_mac_dinh': df['Giá vốn'].apply(clean_numeric),
        'gia_ban_mac_dinh': df['Giá bán'].apply(clean_numeric),
    })
    
    # Loại bỏ duplicate
    products_df = products_df.drop_duplicates(subset=['ma_hang'])
    print(f"✅ Sau khi loại bỏ duplicate: {len(products_df)} sản phẩm")
    
    # Connect PostgreSQL - dùng env vars hoặc default service name
    pg = PostgreSQLConnector(
        host=os.getenv('POSTGRES_HOST', 'postgres'),
        database=os.getenv('POSTGRES_DB', 'retail_db'),
        user=os.getenv('POSTGRES_USER', 'retail_user'),
        password=os.getenv('POSTGRES_PASSWORD', 'retail_password')
    )
    
    # Xóa dữ liệu cũ
    print("🗑️  Xóa dữ liệu products cũ...")
    from sqlalchemy import text
    with pg.get_connection() as conn:
        conn.execute(text("TRUNCATE TABLE products RESTART IDENTITY CASCADE"))
        conn.commit()
    
    # Insert dữ liệu mới
    print("💾 Insert dữ liệu products mới...")
    with pg.get_connection() as conn:
        products_df.to_sql('products', conn, if_exists='append', index=False)
    
    print(f"✅ Đã import {len(products_df)} sản phẩm vào PostgreSQL")


if __name__ == '__main__':
    file_path = sys.argv[1] if len(sys.argv) > 1 else '/csv_input/DanhSachSanPham.csv'
    import_products(file_path)
