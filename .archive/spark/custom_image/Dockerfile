FROM apache/spark:3.5.0

USER root

# Cài đặt dependencies
RUN apt-get update && apt-get install -y wget gcc python3-dev libpq-dev && rm -rf /var/lib/apt/lists/*

# Cài Python packages
RUN pip install --no-cache-dir pandas==2.0.3 openpyxl==3.1.2 xlrd==2.0.1 redis==4.6.0 clickhouse-driver==0.2.6 psycopg2-binary==2.9.7 pyarrow==12.0.1

# Download JDBC drivers
RUN mkdir -p /opt/spark/jars && cd /opt/spark/jars && \
    wget -q https://jdbc.postgresql.org/download/postgresql-42.6.0.jar && \
    wget -q https://repo1.maven.org/maven2/com/clickhouse/clickhouse-jdbc/0.6.0/clickhouse-jdbc-0.6.0-all.jar && \
    wget -q https://repo1.maven.org/maven2/org/apache/commons/commons-lang3/3.12.0/commons-lang3-3.12.0.jar

# Copy ETL scripts
COPY spark_etl_full.py /opt/spark/work-dir/

# Set permissions
RUN chmod +x /opt/spark/work-dir/*.py && \
    chown -R spark:spark /opt/spark/work-dir

# Environment variables
ENV SPARK_CLASSPATH=/opt/spark/jars/*
ENV PYTHONPATH=/opt/spark/python:/opt/spark/work-dir:$PYTHONPATH
ENV PYSPARK_PYTHON=/usr/bin/python3

USER spark
WORKDIR /opt/spark/work-dir
