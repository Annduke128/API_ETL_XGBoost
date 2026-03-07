FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Java for PySpark
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    unixodbc-dev \
    libgssapi-krb5-2 \
    default-jdk \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME for PySpark
ENV JAVA_HOME=/usr/lib/jvm/default-java
ENV PATH=$PATH:$JAVA_HOME/bin

# Download PostgreSQL and ClickHouse JDBC drivers for PySpark
RUN mkdir -p /opt/spark/jars && \
    wget -q -O /opt/spark/jars/postgresql-42.6.0.jar \
    https://jdbc.postgresql.org/download/postgresql-42.6.0.jar && \
    wget -q -O /opt/spark/jars/clickhouse-jdbc-0.6.0-all.jar \
    https://repo1.maven.org/maven2/com/clickhouse/clickhouse-jdbc/0.6.0/clickhouse-jdbc-0.6.0-all.jar

ENV SPARK_CLASSPATH=/opt/spark/jars/postgresql-42.6.0.jar:/opt/spark/jars/clickhouse-jdbc-0.6.0-all.jar

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY *.py .

# Create directories (hỗ trợ cả csv và excel)
RUN mkdir -p /csv_input /csv_output /csv_input/processed /csv_input/error

# Default: run auto processor in continuous mode
CMD ["python", "auto_process_files.py", "--input", "/csv_input", "--output", "/csv_output", "--continuous"]
