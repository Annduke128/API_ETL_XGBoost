#!/usr/bin/env python3
"""
Sync enriched data from PostgreSQL to ClickHouse
Optimized version sử dụng batch processing với DEDUPLICATION
"""

import pandas as pd
from sqlalchemy import create_engine, text
from clickhouse_driver import Client
import argparse
import logging
import os
from typing import List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClickHouseSync:
    """Sync data từ PostgreSQL sang ClickHouse với batch optimization và dedup"""
    
    def __init__(self):
        self.pg_engine = self._get_postgres_engine()
        self.ch_client = self._get_clickhouse_client()
    
    def _get_postgres_engine(self):
        """Create PostgreSQL engine"""
        host = os.getenv('POSTGRES_HOST', 'postgres')
        port = os.getenv('POSTGRES_PORT', '5432')
        db = os.getenv('POSTGRES_DB', 'retail_db')
        user = os.getenv('POSTGRES_USER', 'retail_user')
        password = os.getenv('POSTGRES_PASSWORD', 'retail_password')
        
        return create_engine(
            f'postgresql://{user}:{password}@{host}:{port}/{db}'
        )
    
    def _get_clickhouse_client(self):
        """Create ClickHouse client"""
        host = os.getenv('CLICKHOUSE_HOST', 'clickhouse')
        port = int(os.getenv('CLICKHOUSE_PORT', '9000'))
        db = os.getenv('CLICKHOUSE_DB', 'retail_dw')
        user = os.getenv('CLICKHOUSE_USER', 'default')
        password = os.getenv('CLICKHOUSE_PASSWORD', 'clickhouse_password')
        
        return Client(
            host=host,
            port=port,
            database=db,
            user=user,
            password=password
        )
    
    def truncate_clickhouse_table(self, ch_table: str):
        """Truncate ClickHouse table trước khi sync"""
        try:
            self.ch_client.execute(f"TRUNCATE TABLE {ch_table}")
            logger.info(f"   🗑️  Truncated {ch_table}")
        except Exception as e:
            logger.warning(f"   ⚠️  Could not truncate {ch_table}: {e}")
    
    def sync_table(self, pg_table: str, ch_table: str, batch_size: int = 50000) -> int:
        """Sync một bảng từ PostgreSQL sang ClickHouse"""
        logger.info(f"Syncing {pg_table} -> {ch_table}")
        
        # TRUNCATE ClickHouse table trước
        self.truncate_clickhouse_table(ch_table)
        
        # Get total count
        with self.pg_engine.connect() as conn:
            count_result = conn.execute(text(f"SELECT COUNT(*) FROM {pg_table}"))
            total_rows = count_result.scalar()
        
        logger.info(f"Total rows to sync: {total_rows:,}")
        
        if total_rows == 0:
            logger.warning(f"No data in {pg_table}")
            return 0
        
        # Read in batches
        offset = 0
        total_synced = 0
        
        while offset < total_rows:
            logger.info(f"Reading batch: offset={offset}, limit={batch_size}")
            
            # Read batch from PostgreSQL
            query = f"""
                SELECT * FROM {pg_table}
                ORDER BY id
                LIMIT {batch_size} OFFSET {offset}
            """
            df = pd.read_sql(query, self.pg_engine)
            
            if df.empty:
                break
            
            # Transform và sync sang ClickHouse
            rows_synced = self._sync_batch(df, ch_table)
            total_synced += rows_synced
            
            offset += batch_size
            logger.info(f"Progress: {total_synced:,}/{total_rows:,} rows")
        
        logger.info(f"✅ Synced {total_synced:,} rows to {ch_table}")
        return total_synced
    
    def _sync_batch(self, df: pd.DataFrame, ch_table: str) -> int:
        """Sync một batch dataframe sang ClickHouse"""
        # Clean data
        df = self._clean_for_clickhouse(df)
        
        # Create table if not exists
        self._create_table_if_not_exists(ch_table, df)
        
        # Insert data
        columns = df.columns.tolist()
        data = df.values.tolist()
        
        self.ch_client.execute(
            f"INSERT INTO {ch_table} ({', '.join(columns)}) VALUES",
            data
        )
        
        return len(df)
    
    def _clean_for_clickhouse(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean dataframe cho ClickHouse"""
        df = df.copy()
        
        # Handle NULL values
        for col in df.columns:
            # Check if column has any NULL/NaN values
            has_null = df[col].isna().any()
            
            if df[col].dtype == 'object':
                # Object columns: convert NULL to empty string
                df[col] = df[col].fillna('').astype(str)
            elif pd.api.types.is_integer_dtype(df[col]):
                # Integer columns: convert NULL to 0
                df[col] = df[col].fillna(0).astype(int)
            elif pd.api.types.is_float_dtype(df[col]):
                # Check if this might be a string column with NaN
                if has_null and df[col].dropna().apply(lambda x: isinstance(x, str)).any():
                    # This is actually a string column with NaN values
                    df[col] = df[col].fillna('').astype(str)
                else:
                    # True float column
                    df[col] = df[col].fillna(0.0).astype(float)
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                # Datetime columns: convert NULL to current timestamp
                df[col] = df[col].fillna(pd.Timestamp.now())
            else:
                # For any other type, convert to string to be safe
                if has_null:
                    df[col] = df[col].fillna('').astype(str)
        
        # Additional safety: ensure no NaN values remain
        df = df.where(pd.notna(df), '')
        
        return df
    
    def _create_table_if_not_exists(self, table_name: str, df: pd.DataFrame):
        """Create ClickHouse table from DataFrame schema"""
        columns = []
        for col, dtype in df.dtypes.items():
            ch_type = self._pandas_to_clickhouse_type(dtype)
            columns.append(f"`{col}` {ch_type}")
        
        columns_sql = ',\n    '.join(columns)
        
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {columns_sql}
        ) ENGINE = MergeTree()
        ORDER BY (id)
        """
        
        self.ch_client.execute(create_sql)
    
    def _pandas_to_clickhouse_type(self, dtype) -> str:
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
    
    def run_full_sync(self):
        """Sync all tables"""
        logger.info("="*60)
        logger.info("PostgreSQL → ClickHouse Sync (with DEDUPLICATION)")
        logger.info("="*60)
        
        tables = [
            ('products', 'staging_products'),
            ('transactions', 'staging_transactions'),
            ('transaction_details', 'staging_transaction_details'),
            ('branches', 'staging_branches'),
        ]
        
        total_synced = 0
        for pg_table, ch_table in tables:
            try:
                rows = self.sync_table(pg_table, ch_table)
                total_synced += rows
            except Exception as e:
                logger.error(f"Error syncing {pg_table}: {e}")
                continue
        
        logger.info("="*60)
        logger.info(f"Total synced: {total_synced:,} rows")
        logger.info("="*60)


def main():
    parser = argparse.ArgumentParser(description='Sync PostgreSQL to ClickHouse')
    parser.add_argument('--postgres-url', 
                        default='postgresql://postgres:5432/retail_db',
                        help='PostgreSQL URL')
    
    args = parser.parse_args()
    
    sync = ClickHouseSync()
    sync.run_full_sync()


if __name__ == '__main__':
    main()
