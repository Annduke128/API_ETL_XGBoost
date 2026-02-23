"""
Auto Processor cho CSV và Excel files
Tự động phát hiện và xử lý files mới trong thư mục input
"""

import pandas as pd
from pathlib import Path
import logging
import time
import sys
from datetime import datetime
import hashlib
import shutil
from typing import Dict, List

from data_processor import RetailDataCleaner
from db_connectors import PostgreSQLConnector, ClickHouseConnector
from redis_buffer import RedisBuffer, get_buffer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FileProcessor:
    """Xử lý tự động CSV và Excel files"""
    
    SUPPORTED_EXTENSIONS = {'.csv', '.xlsx', '.xls'}
    
    def __init__(self, input_dir: str = '/csv_input', output_dir: str = '/csv_output'):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.processed_dir = self.input_dir / 'processed'
        self.error_dir = self.input_dir / 'error'
        
        # Ensure directories exist
        self.output_dir.mkdir(exist_ok=True)
        self.processed_dir.mkdir(exist_ok=True)
        self.error_dir.mkdir(exist_ok=True)
        
        # Import os để lấy env vars
        import os
        
        # Initialize connections với env vars
        self.pg = PostgreSQLConnector(
            host=os.getenv('POSTGRES_HOST', 'postgres'),
            port=int(os.getenv('POSTGRES_PORT', '5432')),
            database=os.getenv('POSTGRES_DB', 'retail_db'),
            user=os.getenv('POSTGRES_USER', 'retail_user'),
            password=os.getenv('POSTGRES_PASSWORD', 'retail_password')
        )
        
        self.ch = ClickHouseConnector(
            host=os.getenv('CLICKHOUSE_HOST', 'clickhouse'),
            port=int(os.getenv('CLICKHOUSE_PORT', '9000')),
            database=os.getenv('CLICKHOUSE_DB', 'retail_dw'),
            user=os.getenv('CLICKHOUSE_USER', 'default'),
            password=os.getenv('CLICKHOUSE_PASSWORD', '')
        )
        
        # Redis connection
        self.redis = get_buffer(
            host=os.getenv('REDIS_HOST', 'redis'),
            port=int(os.getenv('REDIS_PORT', '6379'))
        )
        
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
    
    def find_files(self) -> list:
        """Tìm tất cả file CSV và Excel trong thư mục input"""
        files = []
        
        if not self.input_dir.exists():
            logger.error(f"Input directory not found: {self.input_dir}")
            return files
        
        for ext in self.SUPPORTED_EXTENSIONS:
            for file_path in self.input_dir.glob(f'*{ext}'):
                # Bỏ qua file trong thư mục con processed và error
                if 'processed' in str(file_path) or 'error' in str(file_path):
                    continue
                files.append(file_path)
        
        # Sắp xếp theo thờigian tạo (cũ nhất trước)
        files.sort(key=lambda x: x.stat().st_mtime)
        
        return files
    
    def is_already_processed(self, file_path: Path) -> bool:
        """Kiểm tra file đã được xử lý chưa"""
        file_hash = self.calculate_file_hash(file_path)
        return self.redis.is_duplicate(file_hash)
    
    def check_transactions_exist(self, df) -> tuple:
        """
        Kiểm tra giao dịch đã tồn tại trong PostgreSQL chưa
        Trả về: (existing_count, new_count)
        """
        if 'ma_giao_dich' not in df.columns:
            return 0, len(df)
        
        unique_transactions = df['ma_giao_dich'].unique()
        
        from sqlalchemy import text
        with self.pg.get_connection() as conn:
            result = conn.execute(
                text("SELECT ma_giao_dich FROM transactions WHERE ma_giao_dich = ANY(:trans_ids)"),
                {'trans_ids': unique_transactions.tolist()}
            )
            existing = set([row[0] for row in result])
        
        existing_count = len(existing)
        new_count = len(unique_transactions) - existing_count
        
        return existing_count, new_count
    
    def process_file(self, file_path: Path) -> bool:
        """Xử lý một file"""
        filename = file_path.name
        file_hash = self.calculate_file_hash(file_path)
        job_id = f"file_{file_hash[:16]}_{datetime.now().strftime('%H%M%S')}"
        
        logger.info(f"=" * 60)
        logger.info(f"Processing: {filename}")
        logger.info(f"File hash: {file_hash}")
        
        try:
            # Set processing status
            self.redis.set_processing_status(job_id, 'processing', {'file': filename, 'hash': file_hash})
            
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
            output_ext = file_path.suffix.lower()
            if output_ext in ['.xlsx', '.xls']:
                output_filename = f"cleaned_{timestamp}_{file_path.stem}.xlsx"
            else:
                output_filename = f"cleaned_{timestamp}_{filename}"
            output_path = self.output_dir / output_filename
            cleaner.save_cleaned(str(output_path))
            logger.info(f"Saved cleaned file: {output_path}")
            
            # Cache to Redis
            self.redis.cache_dataframe(file_hash, df)
            
            # Check duplicate trong PostgreSQL
            existing, new = self.check_transactions_exist(df)
            if existing > 0:
                logger.warning(f"⚠️  {existing} giao dịch đã tồn tại trong PostgreSQL")
                logger.warning(f"⚠️  {new} giao dịch mới sẽ được thêm")
                
                if new == 0:
                    logger.info(f"✅ Tất cả giao dịch đã tồn tại. Đánh dấu file hoàn thành.")
                    self.redis.set_processing_status(job_id, 'completed_no_new_data', {
                        'file': filename,
                        'existing_transactions': existing
                    })
                    self.stats['processed'] += 1
                    # Di chuyển file vào processed
                    processed_path = self.processed_dir / f"{timestamp}_{filename}"
                    file_path.rename(processed_path)
                    logger.info(f"Moved to processed: {processed_path}")
                    return True
            
            # Insert to PostgreSQL
            logger.info("Inserting to PostgreSQL...")
            self.pg.insert_transactions(df)
            logger.info("PostgreSQL insert completed")
            
            # Insert to ClickHouse
            logger.info("Inserting to ClickHouse...")
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
                'cap_1': 'nhom_hang_cap_1',
                'cap_2': 'nhom_hang_cap_2',
                'cap_3': 'nhom_hang_cap_3',
                'so_luong': 'so_luong',
                'gia_ban': 'gia_ban',
                'gia_von': 'gia_von',
                'loi_nhuan': 'loi_nhuan',
                'tong_tien_hang': 'tong_tien_hang',
                'giam_gia': 'giam_gia',
                'doanh_thu': 'doanh_thu',
                'tong_gia_von': 'tong_gia_von',
                'loi_nhuan_gop': 'loi_nhuan_gop',
                'ty_suat_loi_nhuan': 'ty_suat_loi_nhuan'
            }
            
            ch_df = df.rename(columns=ch_column_mapping)
            required_ch_columns = [
                'thoi_gian', 'ngay', 'ma_giao_dich', 'chi_nhanh', 'ma_hang', 
                'ten_hang', 'so_luong', 'gia_ban', 'gia_von', 'doanh_thu'
            ]
            for col in required_ch_columns:
                if col not in ch_df.columns:
                    ch_df[col] = None
            
            self.ch.insert_dataframe('fact_transactions', ch_df)
            logger.info("ClickHouse insert completed")
            
            # Mark as processed
            self.redis.set_duplicate(file_hash)
            self.redis.set_processing_status(job_id, 'completed', {
                'file': filename,
                'rows_processed': len(df),
                'existing_skipped': existing if existing else 0
            })
            
            # Move to processed
            processed_path = self.processed_dir / f"{timestamp}_{filename}"
            file_path.rename(processed_path)
            logger.info(f"Moved to processed: {processed_path}")
            
            self.stats['processed'] += 1
            logger.info(f"✅ Successfully processed: {filename}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error processing {filename}: {e}")
            self.redis.set_processing_status(job_id, 'error', {'error': str(e)})
            
            # Move to error folder
            error_path = self.error_dir / filename
            shutil.move(str(file_path), str(error_path))
            logger.info(f"Moved to error: {error_path}")
            
            self.stats['errors'] += 1
            return False
    
    def run(self, continuous: bool = False, interval: int = 60) -> Dict:
        """Run processor"""
        logger.info("=" * 60)
        logger.info("🚀 File Auto Processor Started")
        logger.info(f"📁 Input directory: {self.input_dir}")
        logger.info(f"📁 Output directory: {self.output_dir}")
        logger.info(f"📁 Processed directory: {self.processed_dir}")
        logger.info(f"📁 Error directory: {self.error_dir}")
        logger.info(f"📋 Supported formats: {', '.join(self.SUPPORTED_EXTENSIONS)}")
        logger.info("=" * 60)
        
        try:
            while True:
                files = self.find_files()
                self.stats['found'] = len(files)
                
                if files:
                    logger.info(f"\n📂 Found {len(files)} file(s) to process")
                    for i, file_path in enumerate(files, 1):
                        logger.info(f"  {i}. {file_path.name}")
                    
                    for file_path in files:
                        self.process_file(file_path)
                        time.sleep(1)
                else:
                    logger.debug("No new files found")
                
                if not continuous:
                    break
                
                logger.info(f"\n⏳ Waiting {interval}s for new files...")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("\n⚠️ Interrupted by user")
        
        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("📊 PROCESSING SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Files found:    {self.stats['found']}")
        logger.info(f"Processed:      {self.stats['processed']}")
        logger.info(f"Skipped (dup):  {self.stats['skipped']}")
        logger.info(f"Errors:         {self.stats['errors']}")
        logger.info("=" * 60)
        
        return self.stats


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Auto File Processor (CSV & Excel)')
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
