#!/usr/bin/env python
"""Tạo ClickHouse database connection trong Superset"""
import os
import sys
import time

# Đợi Superset sẵn sàng
time.sleep(10)

# Init Flask app
from superset.app import create_app
app = create_app()

with app.app_context():
    from superset.models.core import Database
    from superset.extensions import db
    
    # Check if ClickHouse connection already exists
    existing = db.session.query(Database).filter_by(database_name="ClickHouse_DW").first()
    if existing:
        print("✅ ClickHouse_DW connection already exists!")
        sys.exit(0)
    
    # Create ClickHouse connection
    clickhouse_host = os.getenv('CLICKHOUSE_HOST', 'clickhouse')
    clickhouse_port = os.getenv('CLICKHOUSE_PORT', '8123')
    clickhouse_user = os.getenv('CLICKHOUSE_USER', 'default')
    clickhouse_password = os.getenv('CLICKHOUSE_PASSWORD', 'clickhouse_password')
    clickhouse_db = os.getenv('CLICKHOUSE_DB', 'retail_dw')
    
    # SQLAlchemy URI cho ClickHouse
    sqlalchemy_uri = f"clickhousedb+connect://{clickhouse_user}:{clickhouse_password}@{clickhouse_host}:{clickhouse_port}/{clickhouse_db}"
    
    database = Database(
        database_name="ClickHouse_DW",
        sqlalchemy_uri=sqlalchemy_uri,
        cache_timeout=300,
        expose_in_sqllab=True,
        allow_ctas=True,
        allow_cvas=True,
        allow_dml=True,
    )
    
    db.session.add(database)
    db.session.commit()
    print(f"✅ Created ClickHouse_DW connection: {clickhouse_host}:{clickhouse_port}/{clickhouse_db}")
    
    # Test connection
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(sqlalchemy_uri)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            row = result.fetchone()
            if row and row[0] == 1:
                print("✅ ClickHouse connection test PASSED!")
            else:
                print("⚠️ ClickHouse connection test returned unexpected result")
    except Exception as e:
        print(f"⚠️ ClickHouse connection test failed: {e}")
        # Don't exit with error - connection might still work
