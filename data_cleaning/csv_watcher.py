"""
File watcher để tự động xử lý CSV khi được đưa vào thư mục
"""

import os
import time
import hashlib
import logging
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from csv_processor import RetailDataCleaner, clean_csv
from redis_buffer import get_buffer
from db_connectors import PostgreSQLConnector, ClickHouseConnector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CSVHandler(FileSystemEventHandler):
    """Handler cho sự kiện file system"""
    
    def __init__(self, watch_dir: str, output_dir: str):
        self.watch_dir = watch_dir
        self.output_dir = output_dir
        self.processed_dir = os.path.join(watch_dir, 'processed')
        self.error_dir = os.path.join(watch_dir, 'error')
        
        os.makedirs(self.processed_dir, exist_ok=True)
        os.makedirs(self.error_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)
        
        # Khởi tạo connections
        self.redis = get_buffer(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379))
        )
        
        self.pg = PostgreSQLConnector(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', 5432)),
            database=os.getenv('POSTGRES_DB', 'retail_db'),
            user=os.getenv('POSTGRES_USER', 'retail_user'),
            password=os.getenv('POSTGRES_PASSWORD', 'retail_password')
        )
        
        self.ch = ClickHouseConnector(
            host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
            port=int(os.getenv('CLICKHOUSE_PORT', 9000)),
            database=os.getenv('CLICKHOUSE_DB', 'retail_dw'),
            user=os.getenv('CLICKHOUSE_USER', 'default'),
            password=os.getenv('CLICKHOUSE_PASSWORD', 'clickhouse_password')
        )
    
    def on_created(self, event):
        """Xử lý khi file được tạo"""
        if not event.is_directory and event.src_path.endswith('.csv'):
            logger.info(f"Phát hiện file mới: {event.src_path}")
            self.process_file(event.src_path)
    
    def calculate_file_hash(self, file_path: str) -> str:
        """Tính hash của file"""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def process_file(self, file_path: str):
        """Xử lý file CSV"""
        filename = os.path.basename(file_path)
        file_hash = self.calculate_file_hash(file_path)
        job_id = f"csv_{file_hash[:16]}"
        
        try:
            # Kiểm tra duplicate
            if self.redis.is_duplicate(file_hash):
                logger.warning(f"File {filename} đã được xử lý trước đó")
                os.rename(file_path, os.path.join(self.processed_dir, f"dup_{filename}"))
                return
            
            # Set status
            self.redis.set_processing_status(job_id, 'processing', {'file': filename})
            
            # Đợi file được ghi xong
            time.sleep(2)
            
            # Làm sạch dữ liệu
            cleaner = RetailDataCleaner()
            df = cleaner.clean(file_path)
            stats = cleaner.get_stats()
            
            # Lưu file đã làm sạch
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = os.path.join(self.output_dir, f"cleaned_{timestamp}_{filename}")
            cleaner.save_cleaned(output_path)
            
            # Cache vào Redis
            self.redis.cache_dataframe(file_hash, df)
            
            # Insert vào PostgreSQL (OLTP)
            logger.info("Inserting to PostgreSQL...")
            self.pg.insert_transactions(df)
            
            # Insert vào ClickHouse (Data Warehouse)
            logger.info("Inserting to ClickHouse...")
            # Chọn các cột phù hợp cho ClickHouse
            ch_columns = [
                'thoi_gian', 'ngay', 'thang', 'nam', 'tuan', 'gio', 'thu_trong_tuan',
                'ma_giao_dich', 'chi_nhanh', 'ma_hang', 'ma_vach', 'ten_hang',
                'thuong_hieu', 'cap_1', 'cap_2', 'cap_3',
                'sl', 'gia_ban_sp', 'gia_von_sp', 'loi_nhuan_sp',
                'tong_tien_hang_theo_thoi_gian', 'giam_gia_theo_thoi_gian',
                'doanh_thu_theo_thoi_gian', 'tong_gia_von_theo_thoi_gian',
                'loi_nhuan_gop_theo_thoi_gian', 'tong_loi_nhuan_hang_hoa', 'ty_suat_loi_nhuan'
            ]
            ch_df = df[[col for col in ch_columns if col in df.columns]]
            ch_df = ch_df.rename(columns={'sl': 'so_luong'})
            self.ch.insert_dataframe('fact_transactions', ch_df)
            
            # Cache dedup key
            self.redis.cache_dedup_key(file_hash)
            
            # Update status
            self.redis.set_processing_status(job_id, 'completed', {
                'file': filename,
                'rows_processed': len(df),
                'duplicates_removed': stats.get('duplicates_removed', 0),
                'output_path': output_path
            })
            
            # Move to processed
            processed_path = os.path.join(self.processed_dir, f"{timestamp}_{filename}")
            os.rename(file_path, processed_path)
            
            logger.info(f"Hoàn thành xử lý {filename}: {len(df)} dòng")
            
        except Exception as e:
            logger.error(f"Lỗi xử lý file {filename}: {e}")
            self.redis.set_processing_status(job_id, 'error', {'error': str(e)})
            
            # Move to error
            error_path = os.path.join(self.error_dir, filename)
            os.rename(file_path, error_path)


def start_watcher(watch_dir: str = '/csv_input', output_dir: str = '/csv_output'):
    """Khởi động file watcher"""
    os.makedirs(watch_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    event_handler = CSVHandler(watch_dir, output_dir)
    observer = Observer()
    observer.schedule(event_handler, watch_dir, recursive=False)
    observer.start()
    
    logger.info(f"Watcher đang theo dõi: {watch_dir}")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    
    observer.join()


if __name__ == '__main__':
    import sys
    
    watch_dir = sys.argv[1] if len(sys.argv) > 1 else os.getenv('WATCH_DIR', './csv_input')
    output_dir = sys.argv[2] if len(sys.argv) > 2 else './csv_output'
    
    start_watcher(watch_dir, output_dir)
