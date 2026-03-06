"""
Import file Excel báo cáo bán hàng vào PostgreSQL
Chuyển dữ liệu vào 2 bảng: transactions + transaction_details
"""

import pandas as pd
import sys
import os
import re
from datetime import datetime

sys.path.insert(0, '/app')


def parse_date_from_filename(filename):
    """Trích xuất ngày từ tên file, ví dụ: BaoCaoBanHang_KV06032026 -> 2026-03-06"""
    match = re.search(r'KV(\d{2})(\d{2})(\d{4})', filename)
    if match:
        day, month, year = match.groups()
        try:
            return datetime(int(year), int(month), int(day)).date()
        except:
            pass
    return datetime.now().date()


def clean_numeric(value):
    """Làm sạch giá trị số"""
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    value_str = str(value).replace(',', '').replace('"', '').strip()
    try:
        return float(value_str)
    except:
        return 0.0


def find_column(df, pattern):
    """Tìm tên cột khớp với pattern"""
    for col in df.columns:
        if pattern in col:
            return col
    return None


def import_sales(file_path):
    """Import file Excel báo cáo bán hàng vào transactions + transaction_details"""
    
    print(f"📖 Đọc file: {file_path}")
    filename = os.path.basename(file_path)
    
    from sqlalchemy import text, create_engine
    pg_uri = f"postgresql://{os.getenv('POSTGRES_USER', 'retail_user')}:{os.getenv('POSTGRES_PASSWORD', 'retail_password')}@{os.getenv('POSTGRES_HOST', 'postgres')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'retail_db')}"
    engine = create_engine(pg_uri)
    
    # Đọc file Excel
    try:
        df = pd.read_excel(file_path, engine='openpyxl')
    except Exception as e:
        print(f"❌ Lỗi đọc file Excel: {e}")
        return
    
    print(f"📊 Tổng số dòng: {len(df)}")
    print(f"📋 Các cột: {list(df.columns)}")
    
    if df.empty:
        print("⚠️  File không có dữ liệu")
        return
    
    # Parse ngày từ tên file
    ngay_bao_cao = parse_date_from_filename(filename)
    print(f"📅 Ngày báo cáo: {ngay_bao_cao}")
    
    # Find column names (handle encoding differences)
    col_ma_gd = find_column(df, 'Mã giao dịch')
    col_chi_nhanh = find_column(df, 'Chi nhánh')
    col_thoi_gian = find_column(df, 'Thờ')  # ThờI or Thời
    col_tong_tien = find_column(df, 'Tổng tiền hàng')
    col_giam_gia = find_column(df, 'Giảm giá')
    col_doanh_thu = find_column(df, 'Doanh thu')
    col_gia_von = find_column(df, 'Tổng giá vốn')
    col_loi_nhuan = find_column(df, 'Lợi nhuận gộp')
    col_ma_hang = find_column(df, 'Mã hàng')
    col_ma_vach = find_column(df, 'Mã vạch')
    col_sl = find_column(df, 'SL')
    col_gia_ban = find_column(df, 'Giá bán')
    col_gia_von_sp = find_column(df, 'Giá vốn')
    
    print(f"   Found columns: {col_ma_gd}, {col_chi_nhanh}, {col_thoi_gian}")
    
    # Làm sạch dữ liệu
    print("🧹 Làm sạch dữ liệu...")
    
    # Group by transaction to create transactions records
    agg_dict = {
        col_chi_nhanh: 'first',
        col_tong_tien: 'first',
        col_giam_gia: 'first',
        col_doanh_thu: 'first',
        col_gia_von: 'first',
        col_loi_nhuan: 'first',
    }
    if col_thoi_gian:
        agg_dict[col_thoi_gian] = 'first'
    
    transactions = df.groupby(col_ma_gd).agg(agg_dict).reset_index()
    
    # Xóa dữ liệu cũ cùng ngày
    print(f"🗑️  Xóa dữ liệu cũ cùng ngày {ngay_bao_cao}...")
    with engine.connect() as conn:
        # Xóa transaction_details trước (FK constraint)
        conn.execute(text("""
            DELETE FROM transaction_details 
            WHERE giao_dich_id IN (
                SELECT id FROM transactions 
                WHERE DATE(thoi_gian) = :ngay
            )
        """), {"ngay": ngay_bao_cao})
        
        # Xóa transactions
        conn.execute(text("""
            DELETE FROM transactions 
            WHERE DATE(thoi_gian) = :ngay
        """), {"ngay": ngay_bao_cao})
        conn.commit()
    
    # Insert transactions
    print(f"💾 Insert {len(transactions)} giao dịch...")
    
    with engine.connect() as conn:
        for idx, row in transactions.iterrows():
            # Parse thờI gian
            thoi_gian_str = row.get(col_thoi_gian, '') if col_thoi_gian else ''
            if isinstance(thoi_gian_str, str) and thoi_gian_str:
                try:
                    thoi_gian = pd.to_datetime(thoi_gian_str, dayfirst=True)
                except:
                    thoi_gian = datetime.combine(ngay_bao_cao, datetime.min.time())
            elif isinstance(thoi_gian_str, datetime):
                thoi_gian = thoi_gian_str
            else:
                thoi_gian = datetime.combine(ngay_bao_cao, datetime.min.time())
            
            # Insert transaction
            result = conn.execute(text("""
                INSERT INTO transactions (ma_giao_dich, thoi_gian, tong_tien_hang, giam_gia, doanh_thu, tong_gia_von, loi_nhuan_gop)
                VALUES (:ma_gd, :thoi_gian, :tong_tien, :giam_gia, :doanh_thu, :gia_von, :loi_nhuan)
                ON CONFLICT (ma_giao_dich, thoi_gian) DO UPDATE SET
                    tong_tien_hang = EXCLUDED.tong_tien_hang,
                    giam_gia = EXCLUDED.giam_gia,
                    doanh_thu = EXCLUDED.doanh_thu,
                    tong_gia_von = EXCLUDED.tong_gia_von,
                    loi_nhuan_gop = EXCLUDED.loi_nhuan_gop
                RETURNING id
            """), {
                "ma_gd": str(row[col_ma_gd]),
                "thoi_gian": thoi_gian,
                "tong_tien": clean_numeric(row[col_tong_tien]),
                "giam_gia": clean_numeric(row[col_giam_gia]),
                "doanh_thu": clean_numeric(row[col_doanh_thu]),
                "gia_von": clean_numeric(row[col_gia_von]),
                "loi_nhuan": clean_numeric(row[col_loi_nhuan])
            })
            
            giao_dich_id = result.fetchone()[0]
            
            # Insert transaction_details cho giao dịch này
            details = df[df[col_ma_gd] == row[col_ma_gd]]
            
            for _, detail_row in details.iterrows():
                # Lookup product_id
                ma_hang = str(detail_row.get(col_ma_hang, '')) if col_ma_hang else ''
                ma_vach = str(detail_row.get(col_ma_vach, '')) if col_ma_vach else ''
                
                # Tìm product_id
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
        
        conn.commit()
    
    # Summary
    total_details = len(df)
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"✅ Đã import: {len(transactions)} giao dịch")
    print(f"✅ Chi tiết: {total_details} dòng")
    print(f"📅 Ngày báo cáo: {ngay_bao_cao}")
    print("="*60)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python import_sales.py <excel_file_path>")
        print("Example: python import_sales.py /csv_input/BaoCaoBanHang_KV06032026.xlsx")
        sys.exit(1)
    
    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"❌ File không tồn tại: {file_path}")
        sys.exit(1)
    
    import_sales(file_path)
