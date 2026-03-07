"""
Import DanhSachSanPham.csv vào PostgreSQL (bảng products)
File này chỉ chứa thông tin sản phẩm, không phải giao dịch

Lưu ý: Parsing tên sản phẩm (tách clean_name, weight, unit, packaging_type)
được thực hiện trong DBT (stg_product_variant_parsing.sql)
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
    """Import file DanhSachSanPham - raw data only, no parsing"""
    
    print(f"📖 Đọc file: {file_path}")
    
    # Detect file type and read accordingly
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path, encoding='utf-8-sig')
    elif file_path.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file_path, engine='openpyxl')
    else:
        raise ValueError(f"Không hỗ trợ file format: {file_path}")
    
    print(f"📊 Tổng số sản phẩm: {len(df)}")
    print(f"📋 Các cột: {list(df.columns)}")
    
    # Parse nhóm hàng
    nhom_hang_parsed = df['Nhóm hàng(3 Cấp)'].apply(parse_nhom_hang)
    df['nhom_hang_cap_1'] = [x[0] for x in nhom_hang_parsed]
    df['nhom_hang_cap_2'] = [x[1] for x in nhom_hang_parsed]
    df['nhom_hang_cap_3'] = [x[2] for x in nhom_hang_parsed]
    
    # Mapping cột - KHÔNG parse tên sản phẩm
    products_df = pd.DataFrame({
        'ma_hang': df['Mã hàng'].astype(str),
        'ma_vach': df['Mã vạch'].fillna('').astype(str),
        'ten_hang': df['Tên hàng'].astype(str),           # Raw name, chưa parse
        'thuong_hieu': df['Thương hiệu'].fillna('').astype(str),
        'nhom_hang_cap_1': df['nhom_hang_cap_1'],
        'nhom_hang_cap_2': df['nhom_hang_cap_2'],
        'nhom_hang_cap_3': df['nhom_hang_cap_3'],
        'gia_von_mac_dinh': df['Giá vốn'].apply(clean_numeric),
        'gia_ban_mac_dinh': df['Giá bán'].apply(clean_numeric),
        'ton_nho_nhat': df['Tồn nhỏ nhất'].apply(clean_numeric) if 'Tồn nhỏ nhất' in df.columns else 0.0,
    })
    
    # Loại bỏ duplicate
    products_df = products_df.drop_duplicates(subset=['ma_hang'])
    print(f"✅ Sau khi loại bỏ duplicate: {len(products_df)} sản phẩm")
    print(f"   Parsing sẽ được thực hiện trong DBT")
    
    # Connect PostgreSQL
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
    print(f"   Parsing sẽ được thực hiện trong DBT (stg_product_variant_parsing.sql)")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python import_products.py <file_path>")
        print("Example: python import_products.py /csv_input/DanhSachSanPham.xlsx")
        sys.exit(1)
    
    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"❌ File không tồn tại: {file_path}")
        sys.exit(1)
    
    import_products(file_path)
