# PySpark ETL Dockerfile - Standalone (không cần bitnami/spark)
# Dùng Python base image + PySpark từ pip

FROM python:3.11-slim

USER root

WORKDIR /opt/spark

# Install Java (required for Spark)
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jdk \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set Java home
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
ENV PATH=$JAVA_HOME/bin:$PATH

# Install PySpark và dependencies
RUN pip install --no-cache-dir \
    pyspark==3.5.0 \
    pandas==2.1.4 \
    numpy==1.26.3 \
    pyarrow==14.0.2 \
    psycopg2-binary==2.9.9 \
    clickhouse-driver==0.2.6 \
    openpyxl==3.1.2

# Download PostgreSQL JDBC driver
RUN mkdir -p /opt/spark/jars && \
    wget -q -O /opt/spark/jars/postgresql-42.6.0.jar https://jdbc.postgresql.org/download/postgresql-42.6.0.jar

# Set Spark environment
ENV SPARK_HOME=/usr/local/lib/python3.11/site-packages/pyspark
ENV PYSPARK_PYTHON=python3
ENV PYSPARK_DRIVER_PYTHON=python3
ENV PYTHONPATH=/opt/spark/python:/usr/local/lib/python3.11/site-packages

# Copy PySpark ETL scripts
COPY python_etl /opt/spark/python_etl
COPY python_udfs /opt/spark/python_udfs

# Create directories
RUN mkdir -p /csv_input /csv_output /shared/processed /shared/python_output

# Copy entrypoint
COPY entrypoint.sh /opt/spark/
RUN chmod +x /opt/spark/entrypoint.sh

WORKDIR /opt/spark

ENTRYPOINT ["/opt/spark/entrypoint.sh"]
