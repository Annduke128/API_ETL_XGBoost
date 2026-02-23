"""
⚠️ DEPRECATED: Module này đã được thay thế bởi data_processor.py
Để tương thích ngược, module này import và re-export từ data_processor
"""

import warnings
from data_processor import (
    RetailDataCleaner,
    clean_file,
    # Re-export các hàm và class chính
)

warnings.warn(
    "csv_processor.py đã deprecated. Hãy sử dụng data_processor.py để hỗ trợ cả CSV và Excel",
    DeprecationWarning,
    stacklevel=2
)

# Giữ lại hàm cũ để tương thích
def clean_csv(input_path: str, output_path: str):
    """Wrapper cho backward compatibility"""
    return clean_file(input_path, output_path)

__all__ = ['RetailDataCleaner', 'clean_file', 'clean_csv']
