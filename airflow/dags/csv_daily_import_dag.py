"""
DAG tự động import CSV hàng ngày - CHỈ PostgreSQL
Chạy 1 lần/ngày lúc 2h sáng để xử lý file CSV vào PostgreSQL
Sync sang ClickHouse sẽ do DAG retail_weekly_ml xử lý
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
import logging
import os
import sys

logger = logging.getLogger(__name__)

# Default args
default_args = {
    'owner': 'retail_data_team',
    'depends_on_past': False,
    'email': ['admin@retail.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# DAG definition - Chỉ import vào PostgreSQL
with DAG(
    'csv_daily_import',
    default_args=default_args,
    description='Import CSV từ csv_input vào PostgreSQL (không sync CH)',
    schedule_interval='0 2 * * *',  # Chạy lúc 2h sáng mỗi ngày
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['csv', 'import', 'postgres', 'daily'],
) as dag:

    # Task 1: Kiểm tra có file cần xử lý không
    check_csv_files = BashOperator(
        task_id='check_csv_files',
        bash_command='''
            CSV_COUNT=$(ls -1 /opt/airflow/csv_input/*.csv 2>/dev/null | wc -l)
            XLSX_COUNT=$(ls -1 /opt/airflow/csv_input/*.xlsx 2>/dev/null | wc -l)
            XLS_COUNT=$(ls -1 /opt/airflow/csv_input/*.xls 2>/dev/null | wc -l)
            TOTAL_COUNT=$((CSV_COUNT + XLSX_COUNT + XLS_COUNT))
            if [ $TOTAL_COUNT -eq 0 ]; then
                echo "No files found"
                exit 0
            else
                echo "Found $TOTAL_COUNT files (CSV: $CSV_COUNT, XLSX: $XLSX_COUNT, XLS: $XLS_COUNT)"
                exit 0
            fi
        ''',
    )

    # Task 2: Process files và import vào PostgreSQL
    def process_and_import(**context):
        """Xử lý CSV/Excel và import vào PostgreSQL"""
        sys.path.append('/opt/airflow/data_cleaning')
        
        from data_processor import RetailDataCleaner
        from db_connectors import PostgreSQLConnector
        
        input_dir = '/opt/airflow/csv_input'
        processed_dir = '/opt/airflow/csv_processed'
        os.makedirs(processed_dir, exist_ok=True)
        
        cleaner = RetailDataCleaner()
        pg = PostgreSQLConnector(
            host='postgres',
            database='retail_db',
            user='retail_user',
            password='retail_password'
        )
        
        processed_count = 0
        supported_extensions = ('.csv', '.xlsx', '.xls')
        
        for filename in os.listdir(input_dir):
            if filename.lower().endswith(supported_extensions):
                file_path = os.path.join(input_dir, filename)
                try:
                    # Clean data
                    df = cleaner.clean(file_path)
                    
                    # Insert vào PostgreSQL
                    pg.insert_transactions(df)
                    
                    # Move to processed
                    os.rename(file_path, os.path.join(processed_dir, filename))
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing {filename}: {e}")
                    raise
        
        return f"Processed {processed_count} files into PostgreSQL"

    process_and_import_pg = PythonOperator(
        task_id='process_and_import_pg',
        python_callable=process_and_import,
    )

    # Task 3: Thông báo hoàn thành
    notify_completion = BashOperator(
        task_id='notify_completion',
        bash_command='echo "✅ CSV import to PostgreSQL completed at $(date)"',
    )

    # Dependencies
    check_csv_files >> process_and_import_pg >> notify_completion
