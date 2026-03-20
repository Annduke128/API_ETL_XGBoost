"""
Database connectors for PostgreSQL and ClickHouse
"""

import pandas as pd
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PostgreSQLConnector:
    """Connector for PostgreSQL database"""
    
    def __init__(self, host: str, database: str, user: str, password: str, port: int = 5432):
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.port = port
        self.conn = None
        
    def _get_connection(self):
        """Get database connection"""
        if self.conn is None or self.conn.closed:
            try:
                import psycopg2
            except ImportError:
                logger.error("psycopg2 not installed. Run: pip install psycopg2-binary")
                raise
            self.conn = psycopg2.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password,
                port=self.port
            )
        return self.conn
    
    def execute_query(self, query: str) -> pd.DataFrame:
        """Execute query and return DataFrame"""
        conn = self._get_connection()
        try:
            df = pd.read_sql_query(query, conn)
            return df
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            raise
    
    def insert_transactions(self, df: pd.DataFrame) -> int:
        """Insert transactions from DataFrame"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Assuming df has columns matching transactions table
            # Adjust column names as per your actual schema
            rows_inserted = 0
            
            for _, row in df.iterrows():
                # This is a simplified version - adjust based on actual schema
                cursor.execute("""
                    INSERT INTO transactions 
                    (ma_giao_dich, thoi_gian, chi_nhanh_id, tong_tien_hang, giam_gia, doanh_thu)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ma_giao_dich) DO NOTHING
                """, (
                    row.get('ma_giao_dich'),
                    row.get('thoi_gian'),
                    row.get('chi_nhanh_id'),
                    row.get('tong_tien_hang', 0),
                    row.get('giam_gia', 0),
                    row.get('doanh_thu', 0)
                ))
                rows_inserted += cursor.rowcount
            
            conn.commit()
            logger.info(f"Inserted {rows_inserted} transactions")
            return rows_inserted
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error inserting transactions: {e}")
            raise
        finally:
            cursor.close()
    
    def close(self):
        """Close connection"""
        if self.conn and not self.conn.closed:
            self.conn.close()


class ClickHouseConnector:
    """Connector for ClickHouse database"""
    
    def __init__(self, host: str, database: str, user: str, password: str, port: int = 9000):
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.port = port
        self.client = None
        
    def _get_client(self):
        """Get ClickHouse client"""
        if self.client is None:
            try:
                from clickhouse_driver import Client
            except ImportError:
                logger.error("clickhouse_driver not installed. Run: pip install clickhouse-driver")
                raise
            self.client = Client(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
        return self.client
    
    def insert_dataframe(self, table: str, df: pd.DataFrame) -> int:
        """Insert DataFrame into ClickHouse table"""
        try:
            client = self._get_client()
            
            # Convert DataFrame to list of tuples for ClickHouse
            columns = df.columns.tolist()
            data = df.values.tolist()
            
            client.insert(table, data, columns=columns)
            
            logger.info(f"Inserted {len(df)} rows into {table}")
            return len(df)
            
        except Exception as e:
            logger.error(f"Error inserting to ClickHouse: {e}")
            raise
    
    def execute_query(self, query: str) -> pd.DataFrame:
        """Execute query and return DataFrame"""
        try:
            client = self._get_client()
            result = client.execute(query, with_column_types=True)
            
            data = result[0]
            columns = [col[0] for col in result[1]]
            
            df = pd.DataFrame(data, columns=columns)
            return df
            
        except Exception as e:
            logger.error(f"Error executing ClickHouse query: {e}")
            raise
    
    def close(self):
        """Close connection"""
        if self.client:
            self.client.disconnect()
