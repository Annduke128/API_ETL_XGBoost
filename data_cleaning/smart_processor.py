"""
Smart File Processor - Tự động phát hiện và xử lý file theo quy tắc đặt tên
Thứ tự xử lý: Products → Inventory → Sales → Promotions
"""

import os
import sys
import re
import argparse
from pathlib import Path
from datetime import datetime
import subprocess

sys.path.insert(0, '/app')


# ============================================================================
# FILENAME PATTERNS - Quy tắc phát hiện file
# ============================================================================

USE_SPARK = True  # Toggle: True = PySpark, False = Pandas

FILE_PATTERNS = {
    'products': {
        'patterns': [
            r'(?i)^PRODUCTS[_\-].*\.(xlsx|csv)$',
            r'(?i)^DM_HANGHOA.*\.xlsx$',
            r'(?i)^HANG_HOA[_\-].*\.(xlsx|csv)$',
            r'(?i)^CATALOG[_\-].*\.(xlsx|csv)$',
            r'(?i).*[-_]products[-_].*\.(xlsx|csv)$',
            r'(?i)^DanhSachSanPham.*\.xlsx$',  # Danh sách sản phẩm
            r'(?i)^DANH_SACH_SP.*\.(xlsx|csv)$',  # Danh sách SP
            r'(?i)^DS_SAN_PHAM.*\.(xlsx|csv)$',  # DS sản phẩm
        ],
        'processor': 'import_products_spark.py' if USE_SPARK else 'import_products.py',
        'description': 'Danh mục sản phẩm (PySpark 🔥)' if USE_SPARK else 'Danh mục sản phẩm (Pandas)',
        'priority': 1,
    },
    'inventory': {
        'patterns': [
            r'(?i)^INVENTORY[_\-].*\.(xlsx|csv)$',
            r'(?i)^TON_KHO[_\-].*\.(xlsx|csv)$',
            r'(?i)^BaoCaoXuatNhapTon.*\.xlsx$',
            r'(?i)^XNT[_\-].*\.(xlsx|csv)$',
            r'(?i)^Bao_Cao_XNT.*\.xlsx$',
            r'(?i).*[-_]inventory[-_].*\.(xlsx|csv)$',
            r'(?i)^XUAT_NHAP_TON.*\.xlsx$',
            r'(?i)^BC_XNT.*\.xlsx$',  # NEW: Báo cáo XNT viết tắt
        ],
        'processor': 'import_inventory_spark.py' if USE_SPARK else 'import_inventory.py',
        'description': 'Dữ liệu tồn kho (PySpark 🔥)' if USE_SPARK else 'Dữ liệu tồn kho (Pandas)',
        'priority': 2,
    },
    'sales': {
        'patterns': [
            r'(?i)^BaoCaoBanHang.*\.xlsx$',  # Báo cáo bán hàng (Excel)
            r'(?i)^BaoCaoLoiNhuan.*\.xlsx$',  # Báo cáo lợi nhuận (Excel)
            r'(?i)^BC_BAN_HANG.*\.(xlsx|csv)$',  # BC bán hàng
            r'(?i)^BC_LOI_NHUAN.*\.(xlsx|csv)$',  # BC lợi nhuận
            r'(?i)^BAN_HANG[_\-].*\.(xlsx|csv)$',  # Bán hàng
            r'(?i)^DOANH_THU[_\-].*\.(xlsx|csv)$',  # Doanh thu
        ],
        'processor': 'import_sales_spark.py' if USE_SPARK else 'import_sales.py',
        'description': 'Báo cáo bán hàng (PySpark 🔥)' if USE_SPARK else 'Báo cáo bán hàng (Pandas)',
        'priority': 3,
    },
    'sales_csv': {
        'patterns': [
            r'(?i)^SALES[_\-].*\.csv$',  # Sales CSV
            r'(?i)^TRANSACTION[_\-].*\.csv$',  # Transactions
            r'(?i)^HOA_DON[_\-].*\.csv$',  # Hóa đơn
            r'(?i).*[-_]sales[-_].*\.csv$',  # Pattern sales
            r'(?i)^POS_.*\.csv$',  # POS data
        ],
        'processor': 'auto_process_files.py',
        'description': 'Dữ liệu bán hàng (CSV)',
        'priority': 3,  # Cùng priority với sales
        'extra_args': ['--input', '{input_dir}', '--output', '{output_dir}'],
    },
    'promotions': {
        'patterns': [
            r'(?i)^PROMO[_\-].*\.(csv|xlsx)$',
            r'(?i)^KHUYEN_MAI[_\-].*\.(csv|xlsx)$',
            r'(?i)^DISCOUNT[_\-].*\.(csv|xlsx)$',
            r'(?i)^CTKM[_\-].*\.(csv|xlsx)$',  # Chương trình KM
            r'(?i)^CHUONG_TRINH_KM.*\.(csv|xlsx)$',
            r'(?i).*[-_]promo[-_].*\.(csv|xlsx)$',
            r'(?i)^BaoCaoKhuyenMai.*\.xlsx$',  # NEW: Báo cáo khuyến mãi
            r'(?i)^BC_KHUYEN_MAI.*\.(xlsx|csv)$',  # NEW: BC khuyến mãi
        ],
        'processor': 'import_promotions.py',
        'description': 'Dữ liệu khuyến mãi',
        'priority': 4,  # Xử lý cuối
    },
}


class ProgressReporter:
    """Báo cáo tiến độ với định dạng đẹp"""
    
    def __init__(self):
        self.step = 0
        self.total_steps = 0
        
    def set_total(self, total):
        self.total_steps = total
        
    def report(self, message, emoji="⏳"):
        self.step += 1
        progress = f"[{self.step}/{self.total_steps}]" if self.total_steps > 0 else ""
        print(f"\n{emoji} {progress} {message}")
        print("=" * 60)
        
    def success(self, message):
        print(f"✅ {message}")
        
    def error(self, message):
        print(f"❌ {message}")
        
    def info(self, message):
        print(f"ℹ️  {message}")


class SmartFileClassifier:
    """Phân loại file dựa trên tên"""
    
    def __init__(self):
        self.classified = {key: [] for key in FILE_PATTERNS.keys()}
        self.unknown = []
        
    def classify_file(self, filename):
        """Phân loại một file theo tên"""
        for file_type, config in FILE_PATTERNS.items():
            for pattern in config['patterns']:
                if re.match(pattern, filename):
                    return file_type
        return 'unknown'
    
    def scan_directory(self, directory):
        """Quét thư mục và phân loại tất cả file"""
        input_path = Path(directory)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Thư mục không tồn tại: {directory}")
        
        for file_path in input_path.iterdir():
            if file_path.is_file() and not file_path.name.startswith('.'):
                file_type = self.classify_file(file_path.name)
                
                if file_type == 'unknown':
                    self.unknown.append(file_path)
                else:
                    self.classified[file_type].append(file_path)
        
        # Sắp xếp theo tên file (thường là theo ngày)
        for key in self.classified:
            self.classified[key].sort(key=lambda x: x.name)
            
        return self
    
    def get_processing_order(self):
        """Trả về danh sách file theo thứ tự ưu tiên xử lý"""
        order = []
        
        # Sắp xếp theo priority
        sorted_types = sorted(
            FILE_PATTERNS.items(),
            key=lambda x: x[1]['priority']
        )
        
        for file_type, config in sorted_types:
            files = self.classified[file_type]
            if files:
                order.append({
                    'type': file_type,
                    'files': files,
                    'config': config
                })
                
        return order
    
    def print_summary(self):
        """In tóm tắt phân loại"""
        print("\n" + "=" * 60)
        print("📊 TÓM TẮT PHÂN LOẠI FILE")
        print("=" * 60)
        
        total_files = 0
        for file_type, files in self.classified.items():
            if files:
                config = FILE_PATTERNS[file_type]
                print(f"\n🔹 {config['description']} ({file_type})")
                print(f"   Số lượng: {len(files)} file")
                for f in files:
                    print(f"   • {f.name}")
                total_files += len(files)
        
        if self.unknown:
            print(f"\n⚠️  File chưa phân loại: {len(self.unknown)}")
            for f in self.unknown:
                print(f"   • {f.name}")
        
        print(f"\n📁 Tổng số file: {total_files}")
        print("=" * 60)


def run_processor(processor_name, file_path=None, extra_args=None, working_dir='/app', use_spark=USE_SPARK):
    """Chạy processor script (Python hoặc Spark)"""
    
    if use_spark and 'spark' in processor_name:
        # Mount spark-etl scripts vào container và chạy trực tiếp
        spark_script = f'/app/spark_etl/{processor_name}'
        cmd = ['python', spark_script]
        if file_path:
            cmd.append(str(file_path))
        print(f"   🔥 Chạy PySpark: {processor_name}")
    else:
        # Run with Python
        cmd = ['python', processor_name]
        if file_path:
            cmd.append(str(file_path))
        print(f"   🚀 Chạy Python: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=300  # 5 phút timeout
        )
        
        if result.returncode == 0:
            print(result.stdout)
            return True
        else:
            print(f"   Lỗi: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"   ⏱️  Timeout sau 10 phút")
        return False
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Smart File Processor - Tự động xử lý file theo quy tắc đặt tên'
    )
    parser.add_argument(
        '--input', '-i',
        default='/csv_input',
        help='Thư mục chứa file đầu vào (mặc định: /csv_input)'
    )
    parser.add_argument(
        '--output', '-o',
        default='/csv_output',
        help='Thư mục đầu ra (mặc định: /csv_output)'
    )
    parser.add_argument(
        '--dry-run', '-d',
        action='store_true',
        help='Chỉ hiển thị kế hoạch, không thực sự xử lý'
    )
    parser.add_argument(
        '--type', '-t',
        choices=['products', 'inventory', 'sales', 'promotions', 'all'],
        default='all',
        help='Chỉ xử lý loại file cụ thể'
    )
    parser.add_argument(
        '--sync',
        action='store_true',
        help='Chạy sync to ClickHouse sau khi xử lý xong'
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("🚀 SMART FILE PROCESSOR")
    print("=" * 60)
    print(f"📁 Input:  {args.input}")
    print(f"📁 Output: {args.output}")
    print(f"🔍 Mode:   {'DRY-RUN' if args.dry_run else 'PROCESS'}")
    
    # Step 1: Phân loại file
    print("\n🔍 Bước 1: Quét và phân loại file...")
    classifier = SmartFileClassifier()
    classifier.scan_directory(args.input)
    classifier.print_summary()
    
    # Step 2: Xác định thứ tự xử lý
    processing_order = classifier.get_processing_order()
    
    if not processing_order:
        print("\n⚠️  Không tìm thấy file nào cần xử lý!")
        return
    
    # Lọc theo type nếu cần
    if args.type != 'all':
        processing_order = [p for p in processing_order if p['type'] == args.type]
    
    # Step 3: Xử lý từng loại file
    reporter = ProgressReporter()
    reporter.set_total(len(processing_order) + (1 if args.sync else 0))
    
    success_count = 0
    fail_count = 0
    
    for item in processing_order:
        file_type = item['type']
        files = item['files']
        config = item['config']
        
        reporter.report(
            f"Xử lý: {config['description']}",
            emoji="📦"
        )
        
        if args.dry_run:
            print(f"   [DRY-RUN] Sẽ xử lý {len(files)} file:")
            for f in files:
                print(f"   • {f.name}")
            continue
        
        # Xử lý từng file
        for file_path in files:
            print(f"\n   📄 {file_path.name}")
            
            # Chuẩn bị extra args cho sales processor
            extra_args = None
            if file_type == 'sales' and 'extra_args' in config:
                extra_args = [
                    arg.format(input_dir=args.input, output_dir=args.output)
                    for arg in config['extra_args']
                ]
            
            success = run_processor(
                config['processor'],
                file_path=str(file_path),
                extra_args=extra_args,
                use_spark=USE_SPARK
            )
            
            if success:
                success_count += 1
            else:
                fail_count += 1
    
    # Step 4: Sync to ClickHouse (nếu được yêu cầu)
    if args.sync:
        reporter.report("Sync dữ liệu sang ClickHouse", emoji="🔄")
        
        if args.dry_run:
            print("   [DRY-RUN] Sẽ chạy: python sync_to_clickhouse.py")
        else:
            success = run_processor('sync_to_clickhouse.py')
            if success:
                reporter.success("Sync hoàn tất!")
            else:
                reporter.error("Sync thất bại!")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 KẾT QUẢ XỬ LÝ")
    print("=" * 60)
    reporter.success(f"Thành công: {success_count} file")
    if fail_count > 0:
        reporter.error(f"Thất bại: {fail_count} file")
    print("=" * 60)


if __name__ == '__main__':
    main()
