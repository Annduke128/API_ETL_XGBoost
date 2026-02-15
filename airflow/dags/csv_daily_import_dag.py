"""
DAG tự động import CSV hàng ngày
Chạy 1 lần/ngày lúc 2h sáng để xử lý file CSV từ ngày hôm trước
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.docker.operators.docker import DockerOperator
import logging

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

# DAG definition
with DAG(
    'csv_daily_import',
    default_args=default_args,
    description='Tự động import CSV từ csv_input vào PostgreSQL và ClickHouse hàng ngày',
    schedule_interval='0 2 * * *',  # Chạy lúc 2h sáng mỗi ngày
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['csv', 'import', 'daily'],
) as dag:

    # Task 1: Kiểm tra có file CSV cần xử lý không
    check_csv_files = BashOperator(
        task_id='check_csv_files',
        bash_command='''
            COUNT=$(ls -1 /opt/airflow/csv_input/*.csv 2>/dev/null | wc -l)
            if [ $COUNT -eq 0 ]; then
                echo "No CSV files found"
                exit 0
            else
                echo "Found $COUNT CSV files"
                exit 0
            fi
        ''',
    )

    # Task 2: Process CSV files
    process_csv = DockerOperator(
        task_id='process_csv_files',
        image='retail_csv_processor:latest',
        api_version='auto',
        auto_remove=True,
        command='python auto_process_csv.py --input /csv_input --output /csv_output',
        docker_url='unix://var/run/docker.sock',
        network_mode='retail_network',
        mounts=[
            {'Source': '/home/annduke/retail_data_pipeline/csv_input', 'Target': '/csv_input', 'Type': 'bind'},
            {'Source': '/home/annduke/retail_data_pipeline/csv_output', 'Target': '/csv_output', 'Type': 'bind'},
        ],
        environment={
            'POSTGRES_HOST': 'postgres',
            'POSTGRES_DB': 'retail_db',
            'POSTGRES_USER': 'retail_user',
            'POSTGRES_PASSWORD': 'retail_password',
            'CLICKHOUSE_HOST': 'clickhouse',
            'CLICKHOUSE_DB': 'retail_dw',
            'CLICKHOUSE_USER': 'default',
            'CLICKHOUSE_PASSWORD': 'clickhouse_password',
            'REDIS_HOST': 'redis',
        },
    )

    # Task 3: Chạy DBT để transform dữ liệu sau khi import
    dbt_transform = BashOperator(
        task_id='dbt_transform',
        bash_command='''
            cd /opt/airflow/dbt_retail && \
            dbt run --profiles-dir /opt/airflow/dbt_retail
        ''',
    )

    # Task 4: Thông báo hoàn thành
    notify_completion = BashOperator(
        task_id='notify_completion',
        bash_command='echo "✅ Daily CSV import completed at $(date)"',
    )

    # Dependencies
    check_csv_files >> process_csv >> dbt_transform >> notify_completion
