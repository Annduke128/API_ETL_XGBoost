"""
Data Cleaning Module for Retail Data Pipeline

Các modules chính:
- data_processor: Làm sạch dữ liệu giao dịch
- db_connectors: Kết nối PostgreSQL và ClickHouse
- import_products: Import sản phẩm (raw data, parsing trong DBT)
- sync_to_clickhouse: Sync dữ liệu từ PostgreSQL sang ClickHouse

Lưu ý: Parsing tên sản phẩm được thực hiện trong DBT (stg_product_variant_parsing.sql)
"""

# Data Processor (cần pandas)
try:
    from .data_processor import RetailDataCleaner, clean_file
except ImportError:
    RetailDataCleaner = None
    clean_file = None

# DB connectors (cần sqlalchemy)
try:
    from .db_connectors import PostgreSQLConnector, ClickHouseConnector
except ImportError:
    PostgreSQLConnector = None
    ClickHouseConnector = None

__all__ = [
    # Data Processor
    'RetailDataCleaner',
    'clean_file',
    # DB Connectors
    'PostgreSQLConnector',
    'ClickHouseConnector',
]

__version__ = '2.1.0'
