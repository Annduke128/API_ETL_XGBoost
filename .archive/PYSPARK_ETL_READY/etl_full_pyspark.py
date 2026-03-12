#!/usr/bin/env python3
"""
PySpark ETL Pipeline - Logic từ data_cleaning đã chuyển sang PySpark
"""

import os
import re
import logging
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, lit, current_timestamp, coalesce, trim, sum as spark_sum, expr
)
from pyspark.sql.types import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CSV_INPUT = '/csv_input'

# UDFs từ data_cleaning
@udf(returnType=StructType([
    StructField("cap_1", StringType(), True),
    StructField("cap_2", StringType(), True), 
    StructField("cap_3", StringType(), True)
]))
def parse_nhom_hang_udf(nhom_hang_str):
    """Parse nhóm hàng 3 cấp - logic từ data_cleaning"""
    if not nhom_hang_str:
        return ('', '', '')
    parts = str(nhom_hang_str).split('>>')
    return (
        parts[0].strip() if len(parts) > 0 else '',
        parts[1].strip() if len(parts) > 1 else '',
        parts[2].strip() if len(parts) > 2 else ''
    )

@udf(returnType=DoubleType())
def clean_numeric_udf(value):
    """Clean numeric - logic từ data_cleaning"""
    if value is None:
        return 0.0
    try:
        s = str(value).replace(',', '').replace('"', '').strip()
        return float(s) if s else 0.0
    except:
        return 0.0

def get_spark_session():
    return SparkSession.builder \
        .appName("Retail_ETL") \
        .config("spark.jars", "/opt/spark/jars/postgresql-42.6.0.jar") \
        .getOrCreate()

def parse_date_from_filename(filename):
    match = re.search(r'KV(\d{2})(\d{2})(\d{4})', filename)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"
    return datetime.now().strftime('%Y-%m-%d')

def main():
    spark = get_spark_session()
    logger.info("🚀 PySpark ETL - Logic from data_cleaning")
    # ... (full code đã có ở trên)
    spark.stop()

if __name__ == '__main__':
    main()
