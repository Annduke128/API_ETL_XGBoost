FROM python:3.11-slim

WORKDIR /app

# Cài đặt system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt Python dependencies
COPY docker/ml_pipeline/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tạo thư mục models
RUN mkdir -p /app/models

# Copy source code từ ml_pipeline/
COPY ml_pipeline/*.py .
COPY ml_pipeline/*.yaml .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Default entrypoint
ENTRYPOINT ["python"]
CMD ["xgboost_forecast.py"]
