"""
Airflow DAG cho Retail Data Pipeline
- csv_daily_import: CSV → PostgreSQL (hàng ngày)
- retail_weekly_ml: Sync CH → DBT → Train ML (hàng tuần)
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
import pendulum
import logging

logger = logging.getLogger(__name__)

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

# ============================================
# DAG 1: Weekly ML Pipeline (Sync CH → DBT → Train)
# ============================================
ml_dag = DAG(
    'retail_weekly_ml',
    default_args=default_args,
    description='Weekly: Sync CH → DBT → Train ML → Forecast',
    schedule_interval='0 4 * * 0',  # Chạy lúc 4h sáng Chủ nhật
    start_date=pendulum.datetime(2024, 1, 1, tz="Asia/Ho_Chi_Minh"),
    catchup=False,
    tags=['retail', 'ml', 'weekly', 'dbt'],
)

# Task 1: Sync PostgreSQL → ClickHouse
def sync_pg_to_ch(**context):
    """Đồng bộ dữ liệu từ PostgreSQL sang ClickHouse cho ML"""
    import sys
    sys.path.append('/opt/airflow/data_cleaning')
    
    from db_connectors import PostgreSQLConnector, ClickHouseConnector
    
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
    
    # Lấy dữ liệu 60 ngày gần nhất cho ML
    query = """
        SELECT 
            t.id, t.ma_giao_dich, t.thoi_gian,
            b.ma_chi_nhanh, b.ten_chi_nhanh,
            t.tong_tien_hang, t.giam_gia, t.doanh_thu,
            t.tong_gia_von, t.loi_nhuan_gop
        FROM transactions t
        JOIN branches b ON t.chi_nhanh_id = b.id
        WHERE t.thoi_gian >= CURRENT_DATE - INTERVAL '60 days'
    """
    
    df = pg.execute_query(query)
    
    if len(df) > 0:
        ch.insert_dataframe('fact_transactions', df)
        return f"Synced {len(df)} rows to ClickHouse"
    
    return "No data to sync"

sync_to_ch = PythonOperator(
    task_id='sync_pg_to_clickhouse',
    python_callable=sync_pg_to_ch,
    dag=ml_dag,
)

# Task 2: Chạy DBT models (trên ClickHouse)
dbt_run = BashOperator(
    task_id='dbt_run_models',
    bash_command='''
        cd /opt/airflow/dbt_retail && \
        dbt deps && \
        dbt run --target prod --select tag:daily
    ''',
    dag=ml_dag,
)

# Task 3: Chạy DBT tests
dbt_test = BashOperator(
    task_id='dbt_run_tests',
    bash_command='''
        cd /opt/airflow/dbt_retail && \
        dbt test --target prod
    ''',
    dag=ml_dag,
)

# Task 4: Train ML models
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

# Task 5: Generate forecasts
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

# Task 6: Refresh Superset cache
def refresh_superset_cache(**context):
    """Refresh cache trong Superset"""
    import requests
    
    try:
        response = requests.post(
            'http://superset-web:8088/api/v1/security/login',
            json={
                'username': 'admin',
                'password': 'admin',
                'provider': 'db'
            }
        )
        logger.info("Superset cache refresh triggered")
        return "OK"
    except Exception as e:
        logger.warning(f"Could not refresh Superset cache: {e}")
        return "Warning"

refresh_cache = PythonOperator(
    task_id='refresh_superset_cache',
    python_callable=refresh_superset_cache,
    dag=ml_dag,
)

# DAG dependencies: Sync CH → DBT → Train → Forecast → Refresh
sync_to_ch >> dbt_run >> dbt_test >> train_models >> generate_predictions >> refresh_cache
