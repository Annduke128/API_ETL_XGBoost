from pyspark.sql import SparkSession
from pyspark.sql.functions import udf, col, lit, trim, coalesce, current_timestamp
from pyspark.sql.types import DoubleType, IntegerType
import os

# Initialize Spark
spark = SparkSession.builder.appName("Test").getOrCreate()

# Read the Excel file
import pandas as pd
pdf = pd.read_excel('/csv_input/DanhSachSanPham_KV09032026-142156-201.xlsx', dtype=str)
df = spark.createDataFrame(pdf)

print("Columns:", df.columns)

# Column mapping
col_map = {}
for c in df.columns:
    lc = str(c).lower()
    if 'mã' in lc and 'hàng' in lc:
        col_map['ma_hang'] = c
    elif 'tồn' in lc and ('kho' in lc or 'hiện tại' in lc):
        col_map['current_stock'] = c
        print(f"Found current_stock: {c}")
    elif 'tồn' in lc and ('nhỏ' in lc or 'tối thiểu' in lc):
        col_map['min_stock'] = c
        print(f"Found min_stock: {c}")

print(f"col_map: {col_map}")

# Define UDF
@udf(returnType=DoubleType())
def clean_numeric(value):
    if value is None:
        return 0.0
    try:
        s = str(value).replace(',', '').replace('"', '').strip()
        return float(s) if s else 0.0
    except:
        return 0.0

# Select with UDF
current_stock_col = col_map.get('current_stock')
print(f"Using column: {current_stock_col}")

result = df.select(
    col(col_map['ma_hang']).alias("ma_hang"),
    clean_numeric(col(current_stock_col)).cast("double").alias("current_stock"),
    clean_numeric(col(col_map['min_stock'])).cast("int").alias("min_stock")
).limit(10)

result.show()

# Count non-zero
non_zero = result.filter(col("current_stock") > 0).count()
print(f"Non-zero current_stock count: {non_zero}")
