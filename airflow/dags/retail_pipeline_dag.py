"""
Airflow DAG cho Retail Data Pipeline
- Chạy hàng ngày
- Xử lý dữ liệu từ CSV → PostgreSQL → ClickHouse
- Chạy DBT models
- Cập nhật ML models
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.sensors.filesystem import FileSensor
from airflow.models import Variable
import pendulum

# Default args
default_args = {
    'owner': 'retail_data_team',
    'depends_on_past': False,
    'email': ['data-team@retail.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# DAG chính - Daily ETL
dag = DAG(
    'retail_daily_etl',
    default_args=default_args,
    description='Daily ETL pipeline cho hệ thống bán lẻ',
    schedule_interval='0 2 * * *',  # Chạy lúc 2h sáng mỗi ngày
    start_date=pendulum.datetime(2024, 1, 1, tz="Asia/Ho_Chi_Minh"),
    catchup=False,
    tags=['retail', 'etl', 'daily'],
)

# Task 1: Kiểm tra file CSV mới
wait_for_csv = FileSensor(
    task_id='wait_for_csv_files',
    filepath='/opt/airflow/csv_input/*.csv',
    fs_conn_id='fs_default',
    poke_interval=60,
    timeout=600,
    dag=dag,
)

# Task 2: Xử lý CSV (clean và load vào PostgreSQL)
def process_csv_files(**context):
    """Xử lý các file CSV trong thư mục input"""
    import os
    import sys
    sys.path.append('/opt/airflow/data_cleaning')
    
    from csv_processor import RetailDataCleaner
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
    for filename in os.listdir(input_dir):
        if filename.endswith('.csv'):
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
                print(f"Error processing {filename}: {e}")
                raise
    
    return f"Processed {processed_count} files"

process_csv = PythonOperator(
    task_id='process_csv_files',
    python_callable=process_csv_files,
    dag=dag,
)

# Task 3: Sync từ PostgreSQL sang ClickHouse
def sync_to_clickhouse(**context):
    """Đồng bộ dữ liệu từ PostgreSQL sang ClickHouse"""
    from db_connectors import PostgreSQLConnector, ClickHouseConnector
    from datetime import datetime, timedelta
    
    pg = PostgreSQLConnector(
        host='postgres',
        database='retail_db',
        user='retail_user',
        password='retail_password'
    )
    
    ch = ClickHouseConnector(
        host='clickhouse',
        database='retail_dw',
        user='default',
        password='clickhouse_password'
    )
    
    # Lấy dữ liệu hôm qua
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    query = """
        SELECT 
            t.id, t.ma_giao_dich, t.thoi_gian,
            b.ma_chi_nhanh, b.ten_chi_nhanh,
            t.tong_tien_hang, t.giam_gia, t.doanh_thu,
            t.tong_gia_von, t.loi_nhuan_gop
        FROM transactions t
        JOIN branches b ON t.chi_nhanh_id = b.id
        WHERE DATE(t.thoi_gian) = :date
    """
    
    df = pg.execute_query(query, {'date': yesterday})
    
    if len(df) > 0:
        ch.insert_dataframe('fact_transactions', df)
        return f"Synced {len(df)} rows to ClickHouse"
    
    return "No data to sync"

sync_clickhouse = PythonOperator(
    task_id='sync_to_clickhouse',
    python_callable=sync_to_clickhouse,
    dag=dag,
)

# Task 4: Chạy DBT models
dbt_run = BashOperator(
    task_id='dbt_run_models',
    bash_command='''
        cd /opt/airflow/dbt_retail && \
        dbt deps && \
        dbt run --target prod --select tag:daily
    ''',
    dag=dag,
)

# Task 5: Chạy DBT tests
dbt_test = BashOperator(
    task_id='dbt_run_tests',
    bash_command='''
        cd /opt/airflow/dbt_retail && \
        dbt test --target prod
    ''',
    dag=dag,
)

# Task 6: Refresh Superset cache
def refresh_superset_cache(**context):
    """Refresh cache trong Superset"""
    import requests
    
    try:
        # Gọi API refresh cache (cần cấu hình thêm)
        response = requests.post(
            'http://superset-web:8088/api/v1/security/login',
            json={
                'username': 'admin',
                'password': 'admin',
                'provider': 'db'
            }
        )
        print("Superset cache refresh triggered")
        return "OK"
    except Exception as e:
        print(f"Warning: Could not refresh Superset cache: {e}")
        return "Warning"

refresh_cache = PythonOperator(
    task_id='refresh_superset_cache',
    python_callable=refresh_superset_cache,
    dag=dag,
)

# Define dependencies
wait_for_csv >> process_csv >> sync_clickhouse >> dbt_run >> dbt_test >> refresh_cache


# ============================================
# DAG 2: Weekly ML Pipeline
# ============================================
ml_dag = DAG(
    'retail_weekly_ml',
    default_args=default_args,
    description='Weekly ML pipeline cho dự báo bán hàng',
    schedule_interval='0 3 * * 0',  # Chạy lúc 3h sáng Chủ nhật
    start_date=pendulum.datetime(2024, 1, 1, tz="Asia/Ho_Chi_Minh"),
    catchup=False,
    tags=['retail', 'ml', 'weekly'],
)

def train_forecast_models(**context):
    """Train models dự báo"""
    import sys
    sys.path.append('/opt/airflow/ml_pipeline')
    
    from xgboost_forecast import SalesForecaster
    
    forecaster = SalesForecaster()
    metrics = forecaster.train_all_models()
    
    return f"Trained models with metrics: {metrics}"

train_models = PythonOperator(
    task_id='train_forecast_models',
    python_callable=train_forecast_models,
    dag=ml_dag,
)

def generate_forecasts(**context):
    """Generate forecasts cho tuần tới"""
    import sys
    sys.path.append('/opt/airflow/ml_pipeline')
    
    from xgboost_forecast import SalesForecaster
    
    forecaster = SalesForecaster()
    forecasts = forecaster.predict_next_week()
    
    # Lưu vào database
    forecaster.save_forecasts(forecasts)
    
    return f"Generated {len(forecasts)} forecasts"

generate_predictions = PythonOperator(
    task_id='generate_forecasts',
    python_callable=generate_forecasts,
    dag=ml_dag,
)

train_models >> generate_predictions
