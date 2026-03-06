# Dockerfile cho Retail Spark ETL (Hybrid Approach)
# Stage 1: Build Scala Spark JAR
FROM sbtscala/scala-sbt:eclipse-temurin-17.0.9_9_1.9.9_2.12.17 AS builder

WORKDIR /build

# Copy build files
COPY build.sbt .
COPY project ./project

# Download dependencies (cached layer)
RUN sbt update

# Copy source code
COPY src ./src

# Build fat JAR
RUN sbt assembly

# Stage 2: Runtime image với Spark + Python
FROM docker.io/bitnami/spark:latest

USER root

# Install Python và dependencies cho Pandas UDFs
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-pandas \
    python3-numpy \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install --no-cache-dir \
    pyspark==3.5.0 \
    pandas==2.1.4 \
    numpy==1.26.3 \
    pyarrow==14.0.2 \
    psycopg2-binary==2.9.9 \
    clickhouse-driver==0.2.6

# Copy built JAR from builder
COPY --from=builder /build/target/scala-2.12/retail-spark-etl-assembly-1.0.0.jar /opt/spark/jars/

# Copy Python UDF scripts
COPY python_udfs /opt/spark/python_udfs

# Set environment variables
ENV SPARK_HOME=/opt/bitnami/spark
ENV PYTHONPATH=/opt/spark/python:$PYTHONPATH
ENV PYSPARK_PYTHON=python3
ENV PYSPARK_DRIVER_PYTHON=python3

# Create directories
RUN mkdir -p /csv_input /csv_output /shared/processed /shared/python_output

# Entry point script
COPY entrypoint.sh /opt/spark/
RUN chmod +x /opt/spark/entrypoint.sh

WORKDIR /opt/spark

ENTRYPOINT ["/opt/spark/entrypoint.sh"]
