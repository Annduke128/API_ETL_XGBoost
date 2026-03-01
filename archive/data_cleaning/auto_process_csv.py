"""
⚠️ DEPRECATED: Module này đã được thay thế bởi auto_process_files.py
Để tương thích ngược, module này import và re-export từ auto_process_files
"""

import warnings
import sys
from pathlib import Path

warnings.warn(
    "auto_process_csv.py đã deprecated. Hãy sử dụng auto_process_files.py để hỗ trợ cả CSV và Excel",
    DeprecationWarning,
    stacklevel=2
)

# Import từ module mới
from auto_process_files import FileProcessor

# Giữ lại tên class cũ để tương thích
class CSVProcessor(FileProcessor):
    """Wrapper class cho backward compatibility"""
    pass

# Re-export
__all__ = ['FileProcessor', 'CSVProcessor']

# Nếu chạy trực tiếp, chuyển hướng sang module mới
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Auto File Processor (Deprecated - use auto_process_files.py)')
    parser.add_argument('--input', default='/csv_input', help='Input directory')
    parser.add_argument('--output', default='/csv_output', help='Output directory')
    parser.add_argument('--continuous', action='store_true', help='Run continuously')
    parser.add_argument('--interval', type=int, default=60, help='Check interval (seconds)')
    
    args = parser.parse_args()
    
    processor = FileProcessor(
        input_dir=args.input,
        output_dir=args.output
    )
    
    stats = processor.run(
        continuous=args.continuous,
        interval=args.interval
    )
    
    sys.exit(0 if stats['errors'] == 0 else 1)
