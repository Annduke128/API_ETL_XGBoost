"""
Module làm sạch dữ liệu CSV cho ngành bán lẻ
Hỗ trợ: loại bỏ trùng, thêm dữ liệu thiếu, chuẩn hóa định dạng
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
import hashlib
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RetailDataCleaner:
    """Làm sạch dữ liệu bán lẻ theo chuẩn ngành"""
    
    # Định nghĩa schema chuẩn
    COLUMNS_SCHEMA = {
        'thoi_gian': 'datetime',
        'tong_tien_hang_theo_thoi_gian': 'float',
        'giam_gia_theo_thoi_gian': 'float',
        'doanh_thu_theo_thoi_gian': 'float',
        'tong_gia_von_theo_thoi_gian': 'float',
        'loi_nhuan_gop_theo_thoi_gian': 'float',
        'ma_giao_dich': 'string',
        'chi_nhanh': 'string',
        'thoi_gian_theo_giao_dich': 'datetime',
        'tong_tien_hang_theo_giao_dich': 'float',
        'giam_gia_theo_giao_dich': 'float',
        'doanh_thu_theo_giao_dich': 'float',
        'tong_gia_von_theo_giao_dich': 'float',
        'loi_nhuan_gop_theo_giao_dich': 'float',
        'ma_hang': 'string',
        'ma_vach': 'string',
        'ten_hang': 'string',
        'thuong_hieu': 'string',
        'nhom_hang_3_cap': 'string',
        'sl': 'int',
        'gia_ban_sp': 'float',
        'gia_von_sp': 'float',
        'loi_nhuan_sp': 'float',
        'tong_loi_nhuan_hang_hoa': 'float'
    }
    
    # Mapping tên cột từ tiếng Việt sang snake_case
    # Hỗ trợ cả 2 định dạng: có khoảng trắng và không có khoảng trắng
    COLUMN_MAPPING = {
        # Thờigian
        'Thờigian': 'thoi_gian',
        'Thờigian ': 'thoi_gian',
        'Thờigian(theogiao dịch)': 'thoi_gian_theo_giao_dich',
        'Thờigian(theothờigian)': 'thoi_gian',
        'Thờigian(theothờigian) ': 'thoi_gian',
        # File mẫu mới có khoảng trắng
        'Thờigian': 'thoi_gian',
        'Thờigian (theo thờigian)': 'thoi_gian',
        'Thờigian (theo giao dịch)': 'thoi_gian_theo_giao_dich',
        # Tổng tiền hàng
        'Tổngtiềnhàng(theothờigian)': 'tong_tien_hang_theo_thoi_gian',
        'Tổng tiền hàng (theo thờigian)': 'tong_tien_hang_theo_thoi_gian',
        'Tổngtiềnhàng(theogiao dịch)': 'tong_tien_hang_theo_giao_dich',
        'Tổng tiền hàng (theo giao dịch)': 'tong_tien_hang_theo_giao_dich',
        # Giảm giá
        'Giảmgiá(theothờigian)': 'giam_gia_theo_thoi_gian',
        'Giảm giá (theo thờigian)': 'giam_gia_theo_thoi_gian',
        'Giảmgiá(theogiao dịch)': 'giam_gia_theo_giao_dich',
        'Giảm giá (theo giao dịch)': 'giam_gia_theo_giao_dich',
        # Doanh thu
        'Doanhthu(theothờigian)': 'doanh_thu_theo_thoi_gian',
        'Doanh thu (theo thờigian)': 'doanh_thu_theo_thoi_gian',
        'Doanhthu(theogiao dịch)': 'doanh_thu_theo_giao_dich',
        'Doanh thu (theo giao dịch)': 'doanh_thu_theo_giao_dich',
        # Tổng giá vốn
        'Tổnggiávốn(theothờigian)': 'tong_gia_von_theo_thoi_gian',
        'Tổng giá vốn (theo thờigian)': 'tong_gia_von_theo_thoi_gian',
        'Tổnggiávốn(theogiao dịch)': 'tong_gia_von_theo_giao_dich',
        'Tổng giá vốn (theo giao dịch)': 'tong_gia_von_theo_giao_dich',
        # Lợi nhuận gộp
        'Lợinhậngộp(theothờigian)': 'loi_nhuan_gop_theo_thoi_gian',
        'Lợi nhuận gộp (theo thờigian)': 'loi_nhuan_gop_theo_thoi_gian',
        'Lợinhậngộp(theogiao dịch)': 'loi_nhuan_gop_theo_giao_dich',
        'Lợi nhuận gộp (theo giao dịch)': 'loi_nhuan_gop_theo_giao_dich',
        # Mã giao dịch, Chi nhánh
        'Mãgiao dịch': 'ma_giao_dich',
        'Mã giao dịch': 'ma_giao_dich',
        'Mãgiao dịch ': 'ma_giao_dich',
        'Chinhánh': 'chi_nhanh',
        'Chi nhánh': 'chi_nhanh',
        # Mã hàng, Mã vạch
        'Mãhàng': 'ma_hang',
        'Mã hàng': 'ma_hang',
        'Mãvạch': 'ma_vach',
        'Mã vạch': 'ma_vach',
        # Tên hàng, Thương hiệu
        'Tênhàng': 'ten_hang',
        'Tên hàng': 'ten_hang',
        'Thươnghiệu': 'thuong_hieu',
        'Thương hiệu': 'thuong_hieu',
        # Nhóm hàng
        'Nhómhàng(3Cấp)': 'nhom_hang_3_cap',
        'Nhóm hàng(3 Cấp)': 'nhom_hang_3_cap',
        # Số lượng, Giá
        'SL': 'sl',
        'Giábán/SP': 'gia_ban_sp',
        'Giá bán/SP': 'gia_ban_sp',
        'Giávốn/SP': 'gia_von_sp',
        'Giá vốn/SP': 'gia_von_sp',
        'Lợinhuận/SP': 'loi_nhuan_sp',
        'Lợi nhuận/SP': 'loi_nhuan_sp',
        'Tổnglợinhuậnhàng hóa': 'tong_loi_nhuan_hang_hoa',
        'Tổng lợi nhuận hàng hóa': 'tong_loi_nhuan_hang_hoa',
    }
    
    def __init__(self):
        self.df: Optional[pd.DataFrame] = None
        self.cleaned_df: Optional[pd.DataFrame] = None
        self.stats: Dict = {}
    
    def load_csv(self, file_path: str, encoding: str = 'utf-8') -> pd.DataFrame:
        """Load CSV file với xử lý encoding"""
        encodings_to_try = [encoding, 'utf-8-sig', 'utf-16', 'cp1252']
        
        for enc in encodings_to_try:
            try:
                self.df = pd.read_csv(file_path, encoding=enc)
                logger.info(f"Đã load {len(self.df)} dòng từ {file_path} (encoding: {enc})")
                return self.df
            except UnicodeDecodeError:
                continue
        
        # Nếu tất cả đều fail, thử với errors='ignore'
        self.df = pd.read_csv(file_path, encoding='utf-8', errors='ignore')
        logger.info(f"Đã load {len(self.df)} dòng từ {file_path} (encoding: utf-8 with ignore)")
        return self.df
    
    def normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Chuẩn hóa tên cột về snake_case"""
        # Loại bỏ khoảng trắng đầu/cuối
        df.columns = df.columns.str.strip()
        
        # Map tên cột
        new_columns = []
        for col in df.columns:
            # Thử map trực tiếp trước
            if col in self.COLUMN_MAPPING:
                new_columns.append(self.COLUMN_MAPPING[col])
                continue
            
            # Thử với các biến thể (bỏ khoảng trắng)
            col_clean = col.replace(' ', '').replace('\t', '')
            if col_clean in self.COLUMN_MAPPING:
                new_columns.append(self.COLUMN_MAPPING[col_clean])
                continue
            
            # Nếu không map được, chuyển sang snake_case và bỏ dấu tiếng Việt
            col_snake = self._remove_vietnamese_accents(col)
            col_snake = re.sub(r'[^\w\s]', '', col_snake).strip().lower().replace(' ', '_')
            new_columns.append(col_snake)
        
        df.columns = new_columns
        return df
    
    def _remove_vietnamese_accents(self, text: str) -> str:
        """Bỏ dấu tiếng Việt"""
        import unicodedata
        # Normalize và loại bỏ dấu
        text = unicodedata.normalize('NFD', text)
        text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
        return text
    
    def parse_datetime(self, value) -> Optional[datetime]:
        """Parse datetime từ nhiều định dạng"""
        if pd.isna(value):
            return None
        
        if isinstance(value, datetime):
            return value
        
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%d/%m/%Y %H:%M:%S',
            '%d/%m/%Y %H:%M',
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%m/%d/%Y %H:%M:%S',
            '%m/%d/%Y',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(str(value), fmt)
            except ValueError:
                continue
        
        return None
    
    def clean_numeric(self, value) -> float:
        """Làm sạch giá trị số"""
        if pd.isna(value):
            return 0.0
        
        if isinstance(value, (int, float)):
            return float(value)
        
        # Chuyển sang string và loại bỏ ký tự không phải số
        value_str = str(value).strip()
        
        # Loại bỏ các ký tự tiền tệ và khoảng trắng
        value_str = value_str.replace('đ', '').replace('VNĐ', '').replace('$', '').strip()
        
        # Xử lý định dạng số có dấu phẩy phân cách hàng nghìn
        # Ví dụ: "34,359,000" -> "34359000"
        if ',' in value_str:
            # Kiểm tra nếu dấu phẩy là decimal separator (có dấu chấm hoặc không có gì sau đó)
            parts = value_str.split(',')
            if len(parts) == 2 and len(parts[1]) <= 2:
                # Có thể là decimal separator (ví dụ: 1.234,56 hoặc 1234,56)
                value_str = value_str.replace(',', '.')
            else:
                # Là thousand separator
                value_str = value_str.replace(',', '')
        
        try:
            return float(value_str)
        except ValueError:
            return 0.0
    
    def generate_fingerprint(self, row: pd.Series) -> str:
        """Tạo fingerprint cho việc detect duplicate"""
        key_fields = ['ma_giao_dich', 'ma_hang', 'thoi_gian_theo_giao_dich', 'sl']
        values = []
        for field in key_fields:
            if field in row:
                values.append(str(row[field]))
        
        fingerprint = '|'.join(values)
        return hashlib.md5(fingerprint.encode()).hexdigest()
    
    def remove_duplicates(self, df: pd.DataFrame, subset: Optional[List[str]] = None) -> Tuple[pd.DataFrame, int]:
        """Loại bỏ dòng trùng lặp"""
        initial_count = len(df)
        
        if subset:
            df_clean = df.drop_duplicates(subset=subset, keep='first')
        else:
            # Tạo fingerprint và loại bỏ trùng
            df['fingerprint'] = df.apply(self.generate_fingerprint, axis=1)
            df_clean = df.drop_duplicates(subset=['fingerprint'], keep='first')
            df_clean = df_clean.drop(columns=['fingerprint'])
        
        removed_count = initial_count - len(df_clean)
        logger.info(f"Đã loại bỏ {removed_count} dòng trùng lặp")
        
        return df_clean, removed_count
    
    def fill_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Điền giá trị thiếu"""
        # Điền giá trị mặc định theo loại dữ liệu
        for col, dtype in self.COLUMNS_SCHEMA.items():
            if col not in df.columns:
                continue
            
            if dtype == 'float':
                # Với cột số, điền 0 hoặc giá trị trung bình
                if col in ['gia_ban_sp', 'gia_von_sp']:
                    df[col] = df[col].fillna(0)
                else:
                    df[col] = df[col].fillna(df[col].median() if not df[col].empty else 0)
            
            elif dtype == 'int':
                df[col] = df[col].fillna(0).astype(int)
            
            elif dtype == 'string':
                if col == 'chi_nhanh':
                    df[col] = df[col].fillna('Unknown')
                elif col == 'thuong_hieu':
                    df[col] = df[col].fillna('No Brand')
                else:
                    df[col] = df[col].fillna('')
            
            elif dtype == 'datetime':
                df[col] = df[col].fillna(pd.Timestamp.now())
        
        return df
    
    def validate_data(self, df: pd.DataFrame) -> Dict:
        """Validate dữ liệu và trả về báo cáo"""
        report = {
            'total_rows': len(df),
            'null_counts': df.isnull().sum().to_dict(),
            'duplicates': len(df) - len(df.drop_duplicates()),
            'negative_values': {},
            'outliers': {}
        }
        
        # Kiểm tra giá trị âm
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            negative_count = (df[col] < 0).sum()
            if negative_count > 0:
                report['negative_values'][col] = int(negative_count)
        
        # Kiểm tra outliers (IQR method)
        for col in ['gia_ban_sp', 'gia_von_sp', 'sl']:
            if col in df.columns:
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                outliers = df[(df[col] < Q1 - 1.5 * IQR) | (df[col] > Q3 + 1.5 * IQR)]
                report['outliers'][col] = len(outliers)
        
        return report
    
    def calculate_derived_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Tính toán các trường dẫn xuất"""
        # Tính lợi nhuận/SP nếu thiếu
        if 'loi_nhuan_sp' not in df.columns or df['loi_nhuan_sp'].isna().all():
            if 'gia_ban_sp' in df.columns and 'gia_von_sp' in df.columns:
                df['loi_nhuan_sp'] = df['gia_ban_sp'] - df['gia_von_sp']
            else:
                df['loi_nhuan_sp'] = 0
        
        # Tính tổng lợi nhuận hàng hóa
        if 'tong_loi_nhuan_hang_hoa' not in df.columns or df['tong_loi_nhuan_hang_hoa'].isna().all():
            if 'sl' in df.columns:
                df['tong_loi_nhuan_hang_hoa'] = df['loi_nhuan_sp'] * df['sl']
            else:
                df['tong_loi_nhuan_hang_hoa'] = df['loi_nhuan_sp']
        
        # Tính lợi nhuận gộp theo giao dịch nếu thiếu
        if 'loi_nhuan_gop_theo_giao_dich' not in df.columns or df['loi_nhuan_gop_theo_giao_dich'].isna().all():
            if 'doanh_thu_theo_giao_dich' in df.columns and 'tong_gia_von_theo_giao_dich' in df.columns:
                df['loi_nhuan_gop_theo_giao_dich'] = df['doanh_thu_theo_giao_dich'] - df['tong_gia_von_theo_giao_dich']
            elif 'doanh_thu' in df.columns and 'tong_gia_von' in df.columns:
                df['loi_nhuan_gop_theo_giao_dich'] = df['doanh_thu'] - df['tong_gia_von']
            else:
                df['loi_nhuan_gop_theo_giao_dich'] = 0
        
        # Tính tỷ suất lợi nhuận
        if 'gia_ban_sp' in df.columns:
            df['ty_suat_loi_nhuan'] = df.apply(
                lambda row: (row['loi_nhuan_sp'] / row['gia_ban_sp'] * 100) 
                if row['gia_ban_sp'] > 0 else 0, axis=1
            )
        else:
            df['ty_suat_loi_nhuan'] = 0
        
        # Phân loại nhóm hàng
        if 'nhom_hang_3_cap' in df.columns:
            df['cap_1'] = df['nhom_hang_3_cap'].apply(lambda x: x.split('>')[0].strip() if pd.notna(x) and '>' in x else x)
            df['cap_2'] = df['nhom_hang_3_cap'].apply(
                lambda x: x.split('>')[1].strip() if pd.notna(x) and '>' in x and len(x.split('>')) > 1 else ''
            )
            df['cap_3'] = df['nhom_hang_3_cap'].apply(
                lambda x: x.split('>')[2].strip() if pd.notna(x) and '>' in x and len(x.split('>')) > 2 else ''
            )
        else:
            df['cap_1'] = ''
            df['cap_2'] = ''
            df['cap_3'] = ''
        
        # Thoi gian fields
        if 'thoi_gian' in df.columns:
            df['ngay'] = pd.to_datetime(df['thoi_gian']).dt.date
            df['thang'] = pd.to_datetime(df['thoi_gian']).dt.to_period('M').astype(str)
            df['nam'] = pd.to_datetime(df['thoi_gian']).dt.year
            df['tuan'] = pd.to_datetime(df['thoi_gian']).dt.isocalendar().week
            df['thu_trong_tuan'] = pd.to_datetime(df['thoi_gian']).dt.day_name()
        
        if 'thoi_gian_theo_giao_dich' in df.columns:
            df['gio'] = pd.to_datetime(df['thoi_gian_theo_giao_dich']).dt.hour
        elif 'thoi_gian' in df.columns:
            df['gio'] = pd.to_datetime(df['thoi_gian']).dt.hour
        
        return df
    
    def clean(self, file_path: str, remove_duplicates: bool = True, 
              fill_missing: bool = True) -> pd.DataFrame:
        """Pipeline làm sạch dữ liệu chính"""
        logger.info(f"Bắt đầu làm sạch file: {file_path}")
        
        # Load dữ liệu
        df = self.load_csv(file_path)
        
        # Normalize tên cột
        df = self.normalize_columns(df)
        
        # Làm sạch kiểu dữ liệu
        for col in df.columns:
            if col in self.COLUMNS_SCHEMA:
                dtype = self.COLUMNS_SCHEMA[col]
                if dtype == 'datetime':
                    df[col] = df[col].apply(self.parse_datetime)
                elif dtype == 'float':
                    df[col] = df[col].apply(self.clean_numeric)
                elif dtype == 'int':
                    df[col] = df[col].apply(self.clean_numeric).astype(int)
                elif dtype == 'string':
                    df[col] = df[col].astype(str).replace('nan', '')
        
        # Loại bỏ trùng lặp
        if remove_duplicates:
            df, dup_count = self.remove_duplicates(df)
            self.stats['duplicates_removed'] = dup_count
        
        # Điền giá trị thiếu
        if fill_missing:
            df = self.fill_missing_values(df)
        
        # Tính các trường dẫn xuất
        df = self.calculate_derived_fields(df)
        
        # Validate
        self.stats['validation'] = self.validate_data(df)
        
        self.cleaned_df = df
        logger.info(f"Hoàn thành làm sạch: {len(df)} dòng")
        
        return df
    
    def save_cleaned(self, output_path: str):
        """Lưu dữ liệu đã làm sạch"""
        if self.cleaned_df is None:
            raise ValueError("Chưa có dữ liệu đã làm sạch. Gọi clean() trước.")
        
        self.cleaned_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"Đã lưu dữ liệu sạch vào: {output_path}")
    
    def get_stats(self) -> Dict:
        """Lấy thống kê quá trình làm sạch"""
        return self.stats


# Hàm tiện ích để sử dụng nhanh
def clean_csv(input_path: str, output_path: str) -> pd.DataFrame:
    """Làm sạch CSV và lưu kết quả"""
    cleaner = RetailDataCleaner()
    df = cleaner.clean(input_path)
    cleaner.save_cleaned(output_path)
    return df


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python csv_processor.py <input_csv> <output_csv>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    df = clean_csv(input_file, output_file)
    print(f"Đã xử lý {len(df)} dòng dữ liệu")
