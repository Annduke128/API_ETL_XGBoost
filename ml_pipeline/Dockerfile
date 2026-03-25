FROM python:3.11-slim

WORKDIR /app

# Cài đặt system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tạo thư mục models
RUN mkdir -p /app/models

# Copy source code (trừ xgboost_forecast.py sẽ copy sau)
COPY db_connectors.py .
COPY email_notifier.py .
COPY pipeline_monitor.py .
COPY train_models.py .
COPY *.yaml .

# Copy xgboost_forecast.py SAU CÙNG (quan trọng nhất)
COPY xgboost_forecast.py .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Default entrypoint
ENTRYPOINT ["python"]
CMD ["xgboost_forecast.py"]
