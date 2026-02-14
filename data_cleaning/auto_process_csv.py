"""
Script tự động phát hiện và xử lý file CSV trong thư mục csv_input
- Quét thư mục tìm file CSV
- Kiểm tra file đã xử lý chưa (bằng hash)
- Làm sạch và load vào PostgreSQL + ClickHouse
- Di chuyển file đã xử lý sang processed/
"""

import os
import sys
import hashlib
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/auto_process_csv.log')
    ]
)
logger = logging.getLogger(__name__)

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from csv_processor import RetailDataCleaner
from redis_buffer import get_buffer
from db_connectors import PostgreSQLConnector, ClickHouseConnector


class AutoCSVProcessor:
    """Tự động processor cho CSV files"""
    
    def __init__(self, input_dir: str = '/csv_input', output_dir: str = '/csv_output'):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.processed_dir = self.input_dir / 'processed'
        self.error_dir = self.input_dir / 'error'
        
        # Create directories
        self.output_dir.mkdir(exist_ok=True)
        self.processed_dir.mkdir(exist_ok=True)
        self.error_dir.mkdir(exist_ok=True)
        
        # Initialize connections
        logger.info("Connecting to Redis...")
        self.redis = get_buffer(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379))
        )
        
        logger.info("Connecting to PostgreSQL...")
        self.pg = PostgreSQLConnector(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', 5432)),
            database=os.getenv('POSTGRES_DB', 'retail_db'),
            user=os.getenv('POSTGRES_USER', 'retail_user'),
            password=os.getenv('POSTGRES_PASSWORD', 'retail_password')
        )
        
        logger.info("Connecting to ClickHouse...")
        self.ch = ClickHouseConnector(
            host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
            port=int(os.getenv('CLICKHOUSE_PORT', 9000)),
            database=os.getenv('CLICKHOUSE_DB', 'retail_dw'),
            user=os.getenv('CLICKHOUSE_USER', 'default'),
            password=os.getenv('CLICKHOUSE_PASSWORD', 'clickhouse_password')
        )
        
        # Stats
        self.stats = {
            'found': 0,
            'processed': 0,
            'skipped': 0,
            'errors': 0
        }
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """Tính MD5 hash của file"""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def find_csv_files(self) -> list:
        """Tìm tất cả file CSV trong thư mục input"""
        csv_files = []
        
        if not self.input_dir.exists():
            logger.error(f"Input directory not found: {self.input_dir}")
            return csv_files
        
        for file_path in self.input_dir.glob('*.csv'):
            # Bỏ qua file trong thư mục con processed và error
            if 'processed' in str(file_path) or 'error' in str(file_path):
                continue
            csv_files.append(file_path)
        
        # Sắp xếp theo thờigian tạo (cũ nhất trước)
        csv_files.sort(key=lambda x: x.stat().st_mtime)
        
        return csv_files
    
    def is_already_processed(self, file_path: Path) -> bool:
        """Kiểm tra file đã xử lý chưa"""
        file_hash = self.calculate_file_hash(file_path)
        return self.redis.is_duplicate(file_hash)
    
    def process_file(self, file_path: Path) -> bool:
        """Xử lý một file CSV"""
        filename = file_path.name
        file_hash = self.calculate_file_hash(file_path)
        job_id = f"csv_{file_hash[:16]}_{datetime.now().strftime('%H%M%S')}"
        
        logger.info(f"=" * 60)
        logger.info(f"Processing: {filename}")
        logger.info(f"File hash: {file_hash}")
        
        try:
            # Check duplicate
            if self.redis.is_duplicate(file_hash):
                logger.warning(f"File already processed, skipping: {filename}")
                self.stats['skipped'] += 1
                return True
            
            # Set processing status
            self.redis.set_processing_status(job_id, 'processing', {'file': filename})
            
            # Clean data
            logger.info("Cleaning data...")
            cleaner = RetailDataCleaner()
            df = cleaner.clean(str(file_path))
            clean_stats = cleaner.get_stats()
            
            logger.info(f"Cleaned {len(df)} rows")
            if 'duplicates_removed' in clean_stats:
                logger.info(f"Duplicates removed: {clean_stats['duplicates_removed']}")
            
            # Save cleaned file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f"cleaned_{timestamp}_{filename}"
            output_path = self.output_dir / output_filename
            cleaner.save_cleaned(str(output_path))
            logger.info(f"Saved cleaned file: {output_path}")
            
            # Cache to Redis
            self.redis.cache_dataframe(file_hash, df)
            
            # Insert to PostgreSQL
            logger.info("Inserting to PostgreSQL...")
            self.pg.insert_transactions(df)
            logger.info("PostgreSQL insert completed")
            
            # Insert to ClickHouse
            logger.info("Inserting to ClickHouse...")
            # Mapping từ tên cột DataFrame sang tên cột ClickHouse
            ch_column_mapping = {
                'thoi_gian': 'thoi_gian',
                'ngay': 'ngay',
                'thang': 'thang',
                'nam': 'nam',
                'tuan': 'tuan',
                'gio': 'gio',
                'thu_trong_tuan': 'thu_trong_tuan',
                'ma_giao_dich': 'ma_giao_dich',
                'chi_nhanh': 'chi_nhanh',
                'ma_hang': 'ma_hang',
                'ma_vach': 'ma_vach',
                'ten_hang': 'ten_hang',
                'thuong_hieu': 'thuong_hieu',
                'nhom_hang_cap_1': 'nhom_hang_cap_1',
                'nhom_hang_cap_2': 'nhom_hang_cap_2',
                'nhom_hang_cap_3': 'nhom_hang_cap_3',
                'cap_1': 'cap_1',
                'cap_2': 'cap_2',
                'cap_3': 'cap_3',
                'sl': 'so_luong',
                'so_luong': 'so_luong',
                'gia_ban_sp': 'gia_ban_sp',
                'gia_von_sp': 'gia_von_sp',
                'loi_nhuan_sp': 'loi_nhuan_sp',
                'gia_ban': 'gia_ban',
                'gia_von': 'gia_von',
                'loi_nhuan': 'loi_nhuan',
                'tong_tien_hang': 'tong_tien_hang',
                'tong_tien_hang_theo_thoi_gian': 'tong_tien_hang',
                'giam_gia': 'giam_gia',
                'giam_gia_theo_thoi_gian': 'giam_gia',
                'doanh_thu': 'doanh_thu',
                'doanh_thu_theo_thoi_gian': 'doanh_thu',
                'tong_gia_von': 'tong_gia_von',
                'tong_gia_von_theo_thoi_gian': 'tong_gia_von',
                'loi_nhuan_gop': 'loi_nhuan_gop',
                'loi_nhuan_gop_theo_thoi_gian': 'loi_nhuan_gop',
                'tong_loi_nhuan_hang_hoa': 'tong_loi_nhuan_hang_hoa',
                'ty_suat_loi_nhuan': 'ty_suat_loi_nhuan',
            }
            
            # Chọn các cột có trong cả DataFrame và mapping
            available_cols = [col for col in df.columns if col in ch_column_mapping]
            ch_df = df[available_cols].copy()
            # Rename cột theo mapping
            ch_df = ch_df.rename(columns={col: ch_column_mapping[col] for col in available_cols})
            
            self.ch.insert_dataframe('fact_transactions', ch_df)
            logger.info("ClickHouse insert completed")
            
            # Mark as processed
            self.redis.cache_dedup_key(file_hash)
            
            # Update status
            self.redis.set_processing_status(job_id, 'completed', {
                'file': filename,
                'rows_processed': len(df),
                'output_file': str(output_filename)
            })
            
            # Move to processed
            processed_path = self.processed_dir / f"{timestamp}_{filename}"
            file_path.rename(processed_path)
            logger.info(f"Moved to processed: {processed_path}")
            
            self.stats['processed'] += 1
            logger.info(f"✅ Successfully processed: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error processing {filename}: {e}", exc_info=True)
            self.redis.set_processing_status(job_id, 'error', {'error': str(e)})
            
            # Move to error
            error_path = self.error_dir / filename
            try:
                file_path.rename(error_path)
                logger.info(f"Moved to error folder: {error_path}")
            except Exception as move_err:
                logger.error(f"Could not move file to error folder: {move_err}")
            
            self.stats['errors'] += 1
            return False
    
    def run(self, continuous: bool = False, interval: int = 60):
        """Chạy processor
        
        Args:
            continuous: Nếu True, chạy liên tục và quét định kỳ
            interval: Thờigian chờ giữa các lần quét (giây) nếu continuous=True
        """
        logger.info("=" * 60)
        logger.info("CSV Auto Processor Started")
        logger.info(f"Input directory: {self.input_dir.absolute()}")
        logger.info(f"Output directory: {self.output_dir.absolute()}")
        logger.info(f"Mode: {'Continuous' if continuous else 'One-time'}")
        logger.info("=" * 60)
        
        while True:
            try:
                # Find CSV files
                csv_files = self.find_csv_files()
                self.stats['found'] = len(csv_files)
                
                if csv_files:
                    logger.info(f"Found {len(csv_files)} CSV file(s) to process")
                    
                    for i, file_path in enumerate(csv_files, 1):
                        logger.info(f"\n[{i}/{len(csv_files)}] Processing {file_path.name}")
                        self.process_file(file_path)
                else:
                    logger.info("No CSV files found")
                
                # Print summary
                logger.info("\n" + "=" * 60)
                logger.info("SUMMARY")
                logger.info("=" * 60)
                logger.info(f"Files found:    {self.stats['found']}")
                logger.info(f"Processed:      {self.stats['processed']}")
                logger.info(f"Skipped (dup):  {self.stats['skipped']}")
                logger.info(f"Errors:         {self.stats['errors']}")
                
                if not continuous:
                    break
                
                logger.info(f"\nWaiting {interval}s before next scan...")
                import time
                time.sleep(interval)
                
            except KeyboardInterrupt:
                logger.info("\nShutting down...")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
                if not continuous:
                    break
                time.sleep(interval)
        
        logger.info("Processor stopped")
        return self.stats


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Auto process CSV files')
    parser.add_argument('--input', '-i', default='/csv_input', 
                       help='Input directory (default: /csv_input)')
    parser.add_argument('--output', '-o', default='/csv_output',
                       help='Output directory (default: /csv_output)')
    parser.add_argument('--continuous', '-c', action='store_true',
                       help='Run continuously and watch for new files')
    parser.add_argument('--interval', type=int, default=60,
                       help='Scan interval in seconds (default: 60)')
    
    args = parser.parse_args()
    
    processor = AutoCSVProcessor(
        input_dir=args.input,
        output_dir=args.output
    )
    
    stats = processor.run(
        continuous=args.continuous,
        interval=args.interval
    )
    
    # Return exit code based on errors
    sys.exit(0 if stats['errors'] == 0 else 1)


if __name__ == '__main__':
    main()
