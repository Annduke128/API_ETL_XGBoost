"""
Data processor for cleaning retail CSV/Excel files
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class RetailDataCleaner:
    """Cleaner for retail transaction data from CSV/Excel files"""
    
    def __init__(self):
        self.column_mapping = {
            'Mã giao dịch': 'ma_giao_dich',
            'Thờigian': 'thoi_gian',
            'Mã hàng': 'ma_hang',
            'Tên hàng': 'ten_hang',
            'SL': 'so_luong',
            'ĐVT': 'don_vi_tinh',
            'Đơn giá': 'don_gia',
            'Chi nhánh': 'ma_chi_nhanh',
            'Tổng tiền': 'tong_tien_hang',
            'Giảm giá': 'giam_gia',
            'Doanh thu': 'doanh_thu',
        }
    
    def clean(self, file_path: str) -> pd.DataFrame:
        """
        Clean CSV/Excel file and return standardized DataFrame
        
        Args:
            file_path: Path to CSV or Excel file
            
        Returns:
            Cleaned DataFrame
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Read file based on extension
        if file_path.suffix.lower() == '.csv':
            df = pd.read_csv(file_path)
        elif file_path.suffix.lower() in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")
        
        logger.info(f"Loaded {len(df)} rows from {file_path}")
        
        # Rename columns
        df = df.rename(columns=self.column_mapping)
        
        # Clean numeric columns
        numeric_cols = ['so_luong', 'don_gia', 'tong_tien_hang', 'giam_gia', 'doanh_thu']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Clean datetime
        if 'thoi_gian' in df.columns:
            df['thoi_gian'] = pd.to_datetime(df['thoi_gian'], errors='coerce')
        
        # Remove rows with missing critical data
        df = df.dropna(subset=['ma_giao_dich', 'thoi_gian'], how='any')
        
        logger.info(f"Cleaned data: {len(df)} valid rows")
        return df
    
    def validate(self, df: pd.DataFrame) -> bool:
        """
        Validate cleaned DataFrame
        
        Args:
            df: DataFrame to validate
            
        Returns:
            True if valid, raises exception otherwise
        """
        required_cols = ['ma_giao_dich', 'thoi_gian']
        
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        if len(df) == 0:
            raise ValueError("DataFrame is empty after cleaning")
        
        return True
