#!/bin/bash
# Cài driver ClickHouse trước khi khởi động Superset
echo "Installing ClickHouse driver..."
pip install clickhouse-connect==0.7.19 -q

# Khởi động Superset với gunicorn
echo "Starting Superset..."
exec gunicorn \
    -b 0.0.0.0:8088 \
    --workers 2 \
    --worker-class gthread \
    --threads 4 \
    --timeout 300 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --preload \
    --worker-tmp-dir /dev/shm \
    'superset.app:create_app()'
