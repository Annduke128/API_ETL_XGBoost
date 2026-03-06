"""
Sync raw data từ PostgreSQL sang ClickHouse Staging
Chạy 1 lần duy nhất trước DBT để tối ưu hiệu năng
"""

import pandas as pd
import os
import logging
from sqlalchemy import create_engine, text
from clickhouse_driver import Client as ClickHouseClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_postgres_engine():
    """Tạo PostgreSQL engine"""
    host = os.getenv('POSTGRES_HOST', 'postgres')
    port = os.getenv('POSTGRES_PORT', '5432')
    db = os.getenv('POSTGRES_DB', 'retail_db')
    user = os.getenv('POSTGRES_USER', 'retail_user')
    password = os.getenv('POSTGRES_PASSWORD', 'retail_password')
    
    return create_engine(f'postgresql://{user}:{password}@{host}:{port}/{db}')


def get_clickhouse_client():
    """Tạo ClickHouse client"""
    host = os.getenv('CLICKHOUSE_HOST', 'clickhouse')
    port = int(os.getenv('CLICKHOUSE_PORT', '9000'))  # Native port
    db = os.getenv('CLICKHOUSE_DB', 'retail_dw')
    user = os.getenv('CLICKHOUSE_USER', 'default')
    password = os.getenv('CLICKHOUSE_PASSWORD', 'clickhouse_password')
    
    return ClickHouseClient(
        host=host,
        port=port,
        database=db,
        user=user,
        password=password
    )


def pandas_to_clickhouse_type(dtype):
    """Convert pandas dtype to ClickHouse type"""
    dtype_str = str(dtype).lower()
    
    if 'int64' in dtype_str:
        return 'Int64'
    elif 'int32' in dtype_str or 'int' in dtype_str:
        return 'Int32'
    elif 'float64' in dtype_str:
        return 'Float64'
    elif 'float32' in dtype_str or 'float' in dtype_str:
        return 'Float32'
    elif 'datetime' in dtype_str:
        return 'DateTime'
    elif 'date' in dtype_str:
        return 'Date'
    elif 'bool' in dtype_str:
        return 'UInt8'
    else:
        return 'String'


def create_table_from_df(client, table_name, df):
    """Tạo ClickHouse table từ DataFrame schema"""
    columns = []
    for col, dtype in df.dtypes.items():
        ch_type = pandas_to_clickhouse_type(dtype)
        # Escape column names with special characters
        safe_col = f"`{col}`" if ' ' in col or any(c in col for c in '()-/') else col
        columns.append(f"{safe_col} {ch_type}")
    
    columns_sql = ',\n        '.join(columns)
    
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        {columns_sql}
    ) ENGINE = MergeTree()
    ORDER BY tuple()
    """
    
    client.execute(create_sql)
    logger.info(f"✅ Created table {table_name}")


def insert_dataframe_batch(client, table_name, df, batch_size=5000):
    """Insert DataFrame vào ClickHouse theo batch"""
    columns = df.columns.tolist()
    total_rows = len(df)
    
    # Xử lý NULL values và convert data types cho ClickHouse
    df = df.copy()
    for col in df.columns:
        if df[col].dtype == 'object':
            # Check if this is a date column (contains datetime.date objects)
            non_null = df[col].dropna()
            if len(non_null) > 0:
                first_val = non_null.iloc[0]
                # Check if it's a datetime.date (but not datetime.datetime)
                if type(first_val).__name__ == 'date':
                    # Convert date to string format 'YYYY-MM-DD' for ClickHouse Date type
                    df[col] = df[col].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else '1970-01-01')
                elif type(first_val).__name__ == 'datetime':
                    # Keep as pandas datetime for ClickHouse DateTime type
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                else:
                    # Regular string column
                    df[col] = df[col].fillna('')
            else:
                df[col] = df[col].fillna('')
        elif pd.api.types.is_integer_dtype(df[col]):
            df[col] = df[col].fillna(0)
        elif pd.api.types.is_float_dtype(df[col]):
            df[col] = df[col].fillna(0.0)
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            # Keep as datetime objects for ClickHouse DateTime
            df[col] = df[col].fillna(pd.Timestamp('1970-01-01'))
    
    # Convert DataFrame to list of tuples
    data = df.values.tolist()
    
    # Insert theo batch
    for i in range(0, total_rows, batch_size):
        batch = data[i:i+batch_size]
        client.execute(
            f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES",
            batch
        )
        logger.info(f"   Inserted {min(i+batch_size, total_rows):,}/{total_rows:,} rows")
    
    return total_rows


def sync_table(pg_engine, ch_client, pg_table: str, ch_table: str, skip_empty=True):
    """Đồng bộ 1 bảng từ PostgreSQL sang ClickHouse"""
    logger.info(f"🔄 Đồng bộ {pg_table} -> {ch_table}")
    
    # Extract từ PostgreSQL
    logger.info(f"📥 Reading from PostgreSQL...")
    
    # Check if table exists first
    try:
        check_df = pd.read_sql(f"SELECT 1 FROM {pg_table} LIMIT 1", pg_engine)
    except Exception as e:
        logger.warning(f"⚠️  Bảng {pg_table} không tồn tại hoặc lỗi: {e}")
        return 0
    
    df = pd.read_sql(f"SELECT * FROM {pg_table}", pg_engine)
    
    if df.empty:
        if skip_empty:
            logger.info(f"ℹ️  Bảng {pg_table} rỗng, bỏ qua (skip_empty=True)")
        else:
            logger.warning(f"⚠️  Bảng {pg_table} không có dữ liệu")
        return 0
    
    logger.info(f"📊 Đã extract {len(df):,} dòng, {len(df.columns)} cột")
    logger.info(f"   Columns: {list(df.columns)}")
    
    # Xóa bảng cũ trong ClickHouse nếu tồn tại
    logger.info(f"🗑️  Dropping old table if exists...")
    ch_client.execute(f"DROP TABLE IF EXISTS {ch_table}")
    
    # Tạo bảng mới
    logger.info(f"🏗️  Creating table schema...")
    create_table_from_df(ch_client, ch_table, df)
    
    # Insert dữ liệu theo batch
    logger.info(f"💾 Inserting data...")
    rows = insert_dataframe_batch(ch_client, ch_table, df)
    
    logger.info(f"✅ Đã đồng bộ {rows:,} dòng vào {ch_table}")
    return rows


def main():
    """Đồng bộ tất cả raw tables"""
    
    logger.info("=" * 60)
    logger.info("SYNC POSTGRESQL → CLICKHOUSE STAGING")
    logger.info("=" * 60)
    
    # Tạo connections
    pg_engine = get_postgres_engine()
    ch_client = get_clickhouse_client()
    
    # Test connections
    logger.info("🔌 Testing connections...")
    try:
        with pg_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ PostgreSQL connected")
    except Exception as e:
        logger.error(f"❌ PostgreSQL connection failed: {e}")
        return
    
    try:
        ch_client.execute("SELECT 1")
        logger.info("✅ ClickHouse connected")
    except Exception as e:
        logger.error(f"❌ ClickHouse connection failed: {e}")
        return
    
    total_rows = 0
    
    tables = [
        ('products', 'staging_products'),
        ('transactions', 'staging_transactions'),
        ('transaction_details', 'staging_transaction_details'),
        ('branches', 'staging_branches'),
        ('inventory_transactions', 'staging_inventory_transactions'),
    ]
    
    for pg_table, ch_table in tables:
        try:
            rows = sync_table(pg_engine, ch_client, pg_table, ch_table)
            total_rows += rows
        except Exception as e:
            logger.error(f"❌ Lỗi khi đồng bộ {pg_table}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            continue
    
    logger.info("=" * 60)
    logger.info(f"✅ HOÀN TẤT: Tổng cộng {total_rows:,} dòng đã đồng bộ")
    logger.info("=" * 60)
    
    # Kiểm tra - chỉ kiểm tra các bảng đã được sync thành công
    logger.info("\n📊 Kiểm tra dữ liệu trong ClickHouse:")
    for _, ch_table in tables:
        try:
            # Check if table exists first
            result = ch_client.execute(f"SHOW TABLES LIKE '{ch_table}'")
            if not result:
                logger.info(f"   {ch_table}: (không tồn tại - bảng rỗng hoặc chưa sync)")
                continue
            result = ch_client.execute(f"SELECT COUNT(*) FROM {ch_table}")
            count = result[0][0] if result else 0
            logger.info(f"   {ch_table}: {count:,} dòng")
        except Exception as e:
            logger.info(f"   {ch_table}: (chưa có dữ liệu)")


if __name__ == '__main__':
    main()
