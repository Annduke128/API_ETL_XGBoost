#!/bin/bash
set -e

echo "======================================"
echo "Retail Spark ETL - Hybrid Pipeline"
echo "======================================"

# Default values
INPUT_PATH="${INPUT_PATH:-/csv_input}"
OUTPUT_PATH="${OUTPUT_PATH:-/shared/processed}"
POSTGRES_URL="${POSTGRES_URL:-jdbc:postgresql://postgres:5432/retail_db}"
SPARK_MASTER="${SPARK_MASTER:-spark://spark-master:7077}"
MODE="${MODE:-full}"

echo "Configuration:"
echo "  Input: $INPUT_PATH"
echo "  Output: $OUTPUT_PATH"
echo "  PostgreSQL: $POSTGRES_URL"
echo "  Spark Master: $SPARK_MASTER"
echo "  Mode: $MODE"
echo ""

# Function to import products
try_import_products() {
    echo "📦 Checking for DanhSachSanPham.csv..."
    if [ -f "$INPUT_PATH/DanhSachSanPham.csv" ]; then
        echo "📥 Importing products..."
        python3 /app/import_products.py "$INPUT_PATH/DanhSachSanPham.csv"
    else
        echo "⚠️  DanhSachSanPham.csv not found, skipping product import"
    fi
}

# Function to import inventory
try_import_inventory() {
    echo "📦 Checking for inventory files (BaoCaoXuatNhapTon)..."
    inventory_file=$(find "$INPUT_PATH" -name "*XuatNhapTon*.xlsx" -o -name "*TonKho*.xlsx" 2>/dev/null | head -1)
    if [ -n "$inventory_file" ]; then
        echo "📥 Importing inventory from: $inventory_file"
        python3 /app/import_inventory.py "$inventory_file"
    else
        echo "⚠️  No inventory file found, skipping inventory import"
    fi
}

# Function to run Spark Scala job
run_spark_etl() {
    echo "🚀 Phase 1: Running Spark ETL (Heavy Lifting)..."
    
    spark-submit \
        --master "$SPARK_MASTER" \
        --deploy-mode client \
        --class com.hasu.retail.RetailETL \
        --driver-memory 2g \
        --executor-memory 4g \
        --executor-cores 2 \
        --num-executors 3 \
        --conf spark.sql.adaptive.enabled=true \
        --conf spark.sql.adaptive.coalescePartitions.enabled=true \
        --conf spark.sql.adaptive.skewJoin.enabled=true \
        /opt/spark/jars/retail-spark-etl-assembly-1.0.0.jar \
        "$INPUT_PATH" \
        "$OUTPUT_PATH" \
        "$POSTGRES_URL"
    
    echo "✅ Spark ETL completed"
}

# Function to run Python UDFs
run_python_udfs() {
    echo "🐍 Phase 2: Running Python UDFs (Business Logic)..."
    
    python3 /opt/spark/python_udfs/business_logic_processor.py \
        --input "$OUTPUT_PATH/intermediate" \
        --output "$OUTPUT_PATH/final" \
        --postgres-url "$POSTGRES_URL"
    
    echo "✅ Python UDFs completed"
}

# Function to sync to ClickHouse
sync_to_clickhouse() {
    echo "🔄 Phase 3: Syncing to ClickHouse..."
    
    python3 /opt/spark/python_udfs/sync_to_clickhouse.py \
        --postgres-url "$POSTGRES_URL"
    
    echo "✅ ClickHouse sync completed"
}

# Main execution logic
case "$MODE" in
    products)
        try_import_products
        ;;
    inventory)
        try_import_inventory
        ;;
    spark-only)
        run_spark_etl
        ;;
    python-only)
        run_python_udfs
        ;;
    sync-only)
        sync_to_clickhouse
        ;;
    full|*)
        echo "🔄 Running FULL pipeline..."
        try_import_products
        try_import_inventory
        run_spark_etl
        run_python_udfs
        sync_to_clickhouse
        echo ""
        echo "======================================"
        echo "✅ Full Hybrid Pipeline Completed!"
        echo "======================================"
        ;;
esac
