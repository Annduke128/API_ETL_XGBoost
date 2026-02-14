"""
Database connectors cho PostgreSQL, ClickHouse
"""

import pandas as pd
from sqlalchemy import create_engine, text
from clickhouse_driver import Client as ClickHouseClient
from typing import Dict, List, Optional, Any
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class PostgreSQLConnector:
    """Connector cho PostgreSQL (OLTP Database)"""
    
    def __init__(self, host: str = 'localhost', port: int = 5432,
                 database: str = 'retail_db', user: str = 'postgres',
                 password: str = 'password'):
        self.connection_string = (
            f"postgresql://{user}:{password}@{host}:{port}/{database}"
        )
        self.engine = create_engine(self.connection_string)
    
    @contextmanager
    def get_connection(self):
        """Context manager cho connection"""
        conn = self.engine.connect()
        try:
            yield conn
        finally:
            conn.close()
    
    def init_schema(self):
        """Khởi tạo schema database"""
        ddl = """
        -- Bảng chi nhánh
        CREATE TABLE IF NOT EXISTS branches (
            id SERIAL PRIMARY KEY,
            ma_chi_nhanh VARCHAR(50) UNIQUE NOT NULL,
            ten_chi_nhanh VARCHAR(255),
            dia_chi TEXT,
            thanh_pho VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Bảng danh mục hàng hóa
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            ma_hang VARCHAR(50) UNIQUE NOT NULL,
            ma_vach VARCHAR(100),
            ten_hang VARCHAR(500),
            thuong_hieu VARCHAR(200),
            nhom_hang_cap_1 VARCHAR(200),
            nhom_hang_cap_2 VARCHAR(200),
            nhom_hang_cap_3 VARCHAR(200),
            gia_von_mac_dinh DECIMAL(15,2),
            gia_ban_mac_dinh DECIMAL(15,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Bảng giao dịch (transactions)
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            ma_giao_dich VARCHAR(100) NOT NULL,
            chi_nhanh_id INTEGER REFERENCES branches(id),
            thoi_gian TIMESTAMP NOT NULL,
            tong_tien_hang DECIMAL(15,2),
            giam_gia DECIMAL(15,2),
            doanh_thu DECIMAL(15,2),
            tong_gia_von DECIMAL(15,2),
            loi_nhuan_gop DECIMAL(15,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ma_giao_dich, thoi_gian)
        );
        
        -- Bảng chi tiết giao dịch
        CREATE TABLE IF NOT EXISTS transaction_details (
            id SERIAL PRIMARY KEY,
            giao_dich_id INTEGER REFERENCES transactions(id),
            product_id INTEGER REFERENCES products(id),
            so_luong INTEGER NOT NULL,
            gia_ban DECIMAL(15,2),
            gia_von DECIMAL(15,2),
            loi_nhuan DECIMAL(15,2),
            tong_loi_nhuan DECIMAL(15,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Index cho performance
        CREATE INDEX IF NOT EXISTS idx_transactions_time ON transactions(thoi_gian);
        CREATE INDEX IF NOT EXISTS idx_transactions_branch ON transactions(chi_nhanh_id);
        CREATE INDEX IF NOT EXISTS idx_transaction_details_product ON transaction_details(product_id);
        CREATE INDEX IF NOT EXISTS idx_products_ma_hang ON products(ma_hang);
        """
        
        with self.get_connection() as conn:
            conn.execute(text(ddl))
            conn.commit()
        logger.info("PostgreSQL schema initialized")
    
    def insert_transactions(self, df: pd.DataFrame, batch_size: int = 1000):
        """Insert dữ liệu giao dịch từ DataFrame"""
        
        with self.get_connection() as conn:
            # 1. Insert branches
            branches_df = df[['chi_nhanh']].drop_duplicates()
            branches_df.columns = ['ten_chi_nhanh']
            branches_df['ma_chi_nhanh'] = branches_df['ten_chi_nhanh'].str[:50]
            
            for _, row in branches_df.iterrows():
                conn.execute(text("""
                    INSERT INTO branches (ma_chi_nhanh, ten_chi_nhanh)
                    VALUES (:ma, :ten)
                    ON CONFLICT (ma_chi_nhanh) DO NOTHING
                """), {'ma': row['ma_chi_nhanh'], 'ten': row['ten_chi_nhanh']})
            conn.commit()
            logger.info(f"Inserted {len(branches_df)} branches")
            
            # 2. Insert products
            products_df = df[['ma_hang', 'ma_vach', 'ten_hang', 'thuong_hieu', 
                             'cap_1', 'cap_2', 'cap_3', 'gia_von_sp', 'gia_ban_sp']].drop_duplicates('ma_hang')
            
            for _, row in products_df.iterrows():
                conn.execute(text("""
                    INSERT INTO products (ma_hang, ma_vach, ten_hang, thuong_hieu,
                                        nhom_hang_cap_1, nhom_hang_cap_2, nhom_hang_cap_3,
                                        gia_von_mac_dinh, gia_ban_mac_dinh)
                    VALUES (:ma_hang, :ma_vach, :ten, :th, :c1, :c2, :c3, :gia_von, :gia_ban)
                    ON CONFLICT (ma_hang) DO UPDATE SET
                        ma_vach = EXCLUDED.ma_vach,
                        ten_hang = EXCLUDED.ten_hang,
                        updated_at = CURRENT_TIMESTAMP
                """), {
                    'ma_hang': row['ma_hang'],
                    'ma_vach': row['ma_vach'],
                    'ten': row['ten_hang'],
                    'th': row['thuong_hieu'],
                    'c1': row['cap_1'],
                    'c2': row['cap_2'],
                    'c3': row['cap_3'],
                    'gia_von': row['gia_von_sp'],
                    'gia_ban': row['gia_ban_sp']
                })
            conn.commit()
            logger.info(f"Inserted/Updated {len(products_df)} products")
            
            # 3. Insert transactions
            transactions_df = df[['ma_giao_dich', 'chi_nhanh', 'thoi_gian', 
                                 'tong_tien_hang_theo_thoi_gian', 'giam_gia_theo_thoi_gian',
                                 'doanh_thu_theo_thoi_gian', 'tong_gia_von_theo_thoi_gian',
                                 'loi_nhuan_gop_theo_thoi_gian']].drop_duplicates('ma_giao_dich')
            
            for _, row in transactions_df.iterrows():
                # Lấy branch_id
                branch_result = conn.execute(text(
                    "SELECT id FROM branches WHERE ma_chi_nhanh = :ma"
                ), {'ma': row['chi_nhanh'][:50]}).fetchone()
                
                if branch_result:
                    branch_id = branch_result[0]
                    conn.execute(text("""
                        INSERT INTO transactions 
                        (ma_giao_dich, chi_nhanh_id, thoi_gian, tong_tien_hang, 
                         giam_gia, doanh_thu, tong_gia_von, loi_nhuan_gop)
                        VALUES (:ma_gd, :branch_id, :thoi_gian, :tong_tien, 
                                :giam_gia, :doanh_thu, :tong_gv, :loi_nhuan)
                        ON CONFLICT (ma_giao_dich, thoi_gian) DO NOTHING
                    """), {
                        'ma_gd': row['ma_giao_dich'],
                        'branch_id': branch_id,
                        'thoi_gian': row['thoi_gian'],
                        'tong_tien': row['tong_tien_hang_theo_thoi_gian'],
                        'giam_gia': row['giam_gia_theo_thoi_gian'],
                        'doanh_thu': row['doanh_thu_theo_thoi_gian'],
                        'tong_gv': row['tong_gia_von_theo_thoi_gian'],
                        'loi_nhuan': row['loi_nhuan_gop_theo_thoi_gian']
                    })
            conn.commit()
            logger.info(f"Inserted {len(transactions_df)} transactions")
            
            # 4. Insert transaction details
            for _, row in df.iterrows():
                # Lấy transaction_id
                trans_result = conn.execute(text(
                    "SELECT id FROM transactions WHERE ma_giao_dich = :ma"
                ), {'ma': row['ma_giao_dich']}).fetchone()
                
                # Lấy product_id
                product_result = conn.execute(text(
                    "SELECT id FROM products WHERE ma_hang = :ma"
                ), {'ma': row['ma_hang']}).fetchone()
                
                if trans_result and product_result:
                    conn.execute(text("""
                        INSERT INTO transaction_details 
                        (giao_dich_id, product_id, so_luong, gia_ban, gia_von, 
                         loi_nhuan, tong_loi_nhuan)
                        VALUES (:trans_id, :prod_id, :sl, :gia_ban, :gia_von, 
                                :loi_nhuan, :tong_ln)
                        ON CONFLICT DO NOTHING
                    """), {
                        'trans_id': trans_result[0],
                        'prod_id': product_result[0],
                        'sl': row['sl'],
                        'gia_ban': row['gia_ban_sp'],
                        'gia_von': row['gia_von_sp'],
                        'loi_nhuan': row['loi_nhuan_sp'],
                        'tong_ln': row['tong_loi_nhuan_hang_hoa']
                    })
            conn.commit()
            logger.info(f"Inserted {len(df)} transaction details")
    
    def execute_query(self, query: str, params: Dict = None) -> pd.DataFrame:
        """Execute query và trả về DataFrame"""
        with self.get_connection() as conn:
            return pd.read_sql(text(query), conn, params=params)


class ClickHouseConnector:
    """Connector cho ClickHouse (Data Warehouse)"""
    
    def __init__(self, host: str = 'localhost', port: int = 9000,
                 database: str = 'retail_dw', user: str = 'default',
                 password: str = ''):
        self.client = ClickHouseClient(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        self.database = database
    
    def insert_dataframe(self, table: str, df: pd.DataFrame, batch_size: int = 10000):
        """Insert DataFrame vào ClickHouse"""
        # Chuẩn bị dữ liệu
        columns = df.columns.tolist()
        data = df.values.tolist()
        
        # Insert theo batch
        for i in range(0, len(data), batch_size):
            batch = data[i:i+batch_size]
            self.client.execute(
                f"INSERT INTO {self.database}.{table} ({', '.join(columns)}) VALUES",
                batch
            )
        
        logger.info(f"Inserted {len(df)} rows into {table}")
    
    def query(self, query: str) -> pd.DataFrame:
        """Execute query và trả về DataFrame"""
        result = self.client.execute(query, with_column_types=True)
        data, columns = result
        df = pd.DataFrame(data, columns=[col[0] for col in columns])
        return df



