FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install dbt-core and adapters
# Pin protobuf to 4.25.3 (>=4.0.0 for dbt-core 1.7.0, <5.0.0 for compatibility)
RUN pip install --no-cache-dir \
    protobuf==4.25.3 \
    dbt-core==1.7.0 \
    dbt-postgres==1.7.0 \
    dbt-clickhouse==1.7.0

# Set working directory
WORKDIR /usr/app/dbt

# Copy dbt project files
COPY . .

# Install dbt packages (offline mode - will retry if network available)
RUN dbt deps || echo "Warning: dbt deps failed, will retry at runtime"

# Default command
CMD ["dbt", "run"]
