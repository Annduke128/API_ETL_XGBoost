FROM python:3.11-slim

WORKDIR /app

# Cài đặt system dependencies cho K3s
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

# Copy source code
COPY *.py .
COPY *.yaml .

# Health check cho K8s
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Default entrypoint
ENTRYPOINT ["python"]
CMD ["xgboost_forecast.py"]
