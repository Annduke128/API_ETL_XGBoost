package com.hasu.retail

import org.apache.spark.sql.{SparkSession, DataFrame}
import org.apache.spark.sql.functions._
import org.apache.spark.sql.types._
import org.apache.log4j.Logger

/**
 * Retail ETL Pipeline - Hybrid Approach
 * Spark (Scala) cho heavy lifting, output cho Python UDFs xử lý business logic
 */
object RetailETL {
  
  private val logger = Logger.getLogger(getClass.getName)
  
  // Schema definitions
  val RawSchema: StructType = StructType(Array(
    StructField("Thờigian", StringType, true),
    StructField("Mã giao dịch", StringType, true),
    StructField("Chi nhánh", StringType, true),
    StructField("Mã hàng", StringType, true),
    StructField("Mã vạch", StringType, true),
    StructField("Tên hàng", StringType, true),
    StructField("Thương hiệu", StringType, true),
    StructField("Nhóm hàng(3 Cấp)", StringType, true),
    StructField("SL", IntegerType, true),
    StructField("Giá bán/SP", DecimalType(15,2), true),
    StructField("Giá vốn/SP", DecimalType(15,2), true),
    StructField("Tổng tiền hàng (theo thờigian)", DecimalType(15,2), true),
    StructField("Giảm giá (theo thờigian)", DecimalType(15,2), true),
    StructField("Doanh thu (theo thờigian)", DecimalType(15,2), true),
    StructField("Tổng giá vốn (theo thờigian)", DecimalType(15,2), true),
    StructField("Lợi nhuận gộp (theo thờigian)", DecimalType(15,2), true)
  ))
  
  // Column name mapping (Vietnamese -> snake_case)
  val ColumnMapping: Map[String, String] = Map(
    "Thờigian" -> "thoi_gian_raw",
    "Mã giao dịch" -> "ma_giao_dich",
    "Chi nhánh" -> "chi_nhanh",
    "Mã hàng" -> "ma_hang",
    "Mã vạch" -> "ma_vach",
    "Tên hàng" -> "ten_hang",
    "Thương hiệu" -> "thuong_hieu",
    "Nhóm hàng(3 Cấp)" -> "nhom_hang_3_cap",
    "SL" -> "so_luong",
    "Giá bán/SP" -> "gia_ban_sp",
    "Giá vốn/SP" -> "gia_von_sp",
    "Tổng tiền hàng (theo thờigian)" -> "tong_tien_hang",
    "Giảm giá (theo thờigian)" -> "giam_gia",
    "Doanh thu (theo thờigian)" -> "doanh_thu",
    "Tổng giá vốn (theo thờigian)" -> "tong_gia_von",
    "Lợi nhuận gộp (theo thờigian)" -> "loi_nhuan_gop"
  )
  
  def main(args: Array[String]): Unit = {
    
    val inputPath = args.lift(0).getOrElse("/csv_input")
    val outputPath = args.lift(1).getOrElse("/shared/processed")
    val postgresUrl = args.lift(2).getOrElse("jdbc:postgresql://postgres:5432/retail_db")
    
    logger.info("="*60)
    logger.info("RETAIL SPARK ETL - Hybrid Architecture")
    logger.info("="*60)
    logger.info(s"Input: $inputPath")
    logger.info(s"Output: $outputPath")
    logger.info(s"PostgreSQL: $postgresUrl")
    
    // Initialize Spark Session với optimizations
    val spark = SparkSession.builder()
      .appName("RetailSparkETL")
      .config("spark.sql.adaptive.enabled", "true")
      .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
      .config("spark.sql.adaptive.skewJoin.enabled", "true")
      .config("spark.sql.optimizer.dynamicPartitionPruning.enabled", "true")
      .config("spark.sql.files.maxPartitionBytes", "134217728") // 128MB
      .config("spark.default.parallelism", "16")
      .config("spark.sql.shuffle.partitions", "16")
      .getOrCreate()
    
    import spark.implicits._
    
    try {
      // ==================== PHASE 1: Data Ingestion ====================
      logger.info("PHASE 1: Loading CSV files...")
      val rawDF = loadCSV(spark, inputPath)
      logger.info(s"Loaded ${rawDF.count()} raw rows")
      
      // ==================== PHASE 2: Basic Cleaning ====================
      logger.info("PHASE 2: Basic cleaning (Spark distributed)...")
      val cleanedDF = basicCleaning(rawDF)
      logger.info(s"After cleaning: ${cleanedDF.count()} rows")
      
      // ==================== PHASE 3: Deduplication ====================
      logger.info("PHASE 3: Distributed deduplication...")
      val dedupedDF = deduplicate(cleanedDF)
      logger.info(s"After dedup: ${dedupedDF.count()} rows")
      
      // ==================== PHASE 4: Enrichment ====================
      logger.info("PHASE 4: Data enrichment...")
      val enrichedDF = enrichData(dedupedDF)
      
      // ==================== PHASE 5: Write for Python UDFs ====================
      logger.info("PHASE 5: Writing to shared storage for Python UDFs...")
      writeForPythonUDFs(enrichedDF, outputPath)
      
      // ==================== PHASE 6: Write to PostgreSQL ====================
      logger.info("PHASE 6: Writing to PostgreSQL...")
      writeToPostgreSQL(enrichedDF, postgresUrl)
      
      logger.info("="*60)
      logger.info("ETL COMPLETED SUCCESSFULLY")
      logger.info("="*60)
      logger.info(s"Next: Run Python UDFs on $outputPath")
      
    } catch {
      case e: Exception =>
        logger.error("ETL FAILED", e)
        throw e
    } finally {
      spark.stop()
    }
  }
  
  /**
   * Load CSV files với schema inference và partitioning
   */
  def loadCSV(spark: SparkSession, path: String): DataFrame = {
    spark.read
      .option("header", "true")
      .option("encoding", "UTF-8")
      .option("multiLine", "true")
      .option("escape", "\"")
      .schema(RawSchema) // Pre-defined schema for performance
      .csv(s"$path/*.csv")
      .repartition(col("Chi nhánh")) // Partition by branch for locality
  }
  
  /**
   * Basic cleaning: null handling, type conversion, column renaming
   * Đây là heavy lifting - chạy distributed trên tất cả workers
   */
  def basicCleaning(df: DataFrame): DataFrame = {
    var result = df
    
    // Rename columns
    ColumnMapping.foreach { case (oldName, newName) =>
      if (df.columns.contains(oldName)) {
        result = result.withColumnRenamed(oldName, newName)
      }
    }
    
    // Clean datetime
    result = result
      .withColumn("thoi_gian", to_timestamp(col("thoi_gian_raw"), "dd/MM/yyyy HH:mm:ss"))
      .withColumn("ngay", to_date(col("thoi_gian")))
      .withColumn("thang", date_format(col("thoi_gian"), "yyyy-MM"))
      .withColumn("nam", year(col("thoi_gian")))
      .withColumn("tuan", weekofyear(col("thoi_gian")))
      .withColumn("gio", hour(col("thoi_gian")))
      .drop("thoi_gian_raw")
    
    // Clean numeric columns - replace nulls with 0
    val numericCols = Seq("gia_ban_sp", "gia_von_sp", "so_luong", "doanh_thu", "giam_gia")
    numericCols.foreach { colName =>
      if (result.columns.contains(colName)) {
        result = result.withColumn(colName, coalesce(col(colName), lit(0)))
      }
    }
    
    // Clean string columns - replace nulls with empty string
    val stringCols = Seq("ma_hang", "ten_hang", "thuong_hieu", "chi_nhanh")
    stringCols.foreach { colName =>
      if (result.columns.contains(colName)) {
        result = result.withColumn(colName, coalesce(col(colName), lit("")))
      }
    }
    
    // Calculate derived fields (distributed - no apply!)
    result = result
      .withColumn("loi_nhuan_sp", col("gia_ban_sp") - col("gia_von_sp"))
      .withColumn("ty_suat_loi_nhuan", 
        when(col("gia_ban_sp") > 0, 
          (col("loi_nhuan_sp") / col("gia_ban_sp")) * 100
        ).otherwise(0.0)
      )
      .withColumn("tong_loi_nhuan_hang_hoa", col("loi_nhuan_sp") * col("so_luong"))
    
    // Add processing metadata
    result = result
      .withColumn("_processing_timestamp", current_timestamp())
      .withColumn("_source_file", input_file_name())
    
    result
  }
  
  /**
   * Distributed deduplication sử dụng hash
   */
  def deduplicate(df: DataFrame): DataFrame = {
    // Create fingerprint for deduplication
    val withFingerprint = df.withColumn("_fingerprint", 
      md5(concat_ws("|", 
        col("ma_giao_dich"), 
        col("ma_hang"), 
        col("thoi_gian"),
        col("so_luong")
      ))
    )
    
    // Drop duplicates based on fingerprint (distributed across partitions)
    withFingerprint.dropDuplicates("_fingerprint")
      .drop("_fingerprint")
  }
  
  /**
   * Data enrichment: Split nhóm hàng, add flags, etc.
   */
  def enrichData(df: DataFrame): DataFrame = {
    var result = df
    
    // Split nhom_hang_3_cap into separate columns
    if (df.columns.contains("nhom_hang_3_cap")) {
      result = result
        .withColumn("cap_1", split(col("nhom_hang_3_cap"), ">").getItem(0))
        .withColumn("cap_2", 
          when(split(col("nhom_hang_3_cap"), ">").getItem(1).isNotNull,
            trim(split(col("nhom_hang_3_cap"), ">").getItem(1))
          ).otherwise(lit(""))
        )
        .withColumn("cap_3", 
          when(split(col("nhom_hang_3_cap"), ">").getItem(2).isNotNull,
            trim(split(col("nhom_hang_3_cap"), ">").getItem(2))
          ).otherwise(lit(""))
        )
    }
    
    // Add high-value transaction flag (for Python UDF to expand on)
    result = result
      .withColumn("_is_high_value", when(col("doanh_thu") > 1000000, true).otherwise(false))
      .withColumn("_is_negative_margin", when(col("loi_nhuan_sp") < 0, true).otherwise(false))
    
    result
  }
  
  /**
   * Write Parquet files for Python UDFs to process business logic
   */
  def writeForPythonUDFs(df: DataFrame, path: String): Unit = {
    df.write
      .mode("overwrite")
      .parquet(s"$path/intermediate")
    
    logger.info(s"Written intermediate data to $path/intermediate")
    
    // Also write a summary for Python to know what to process
    val summary = df.groupBy("chi_nhanh")
      .agg(
        count("*").alias("total_records"),
        sum("doanh_thu").alias("total_revenue"),
        min("ngay").alias("min_date"),
        max("ngay").alias("max_date")
      )
    
    summary.write
      .mode("overwrite")
      .json(s"$path/summary")
    
    logger.info(s"Written summary to $path/summary")
  }
  
  /**
   * Write to PostgreSQL sử dụng JDBC
   */
  def writeToPostgreSQL(df: DataFrame, url: String): Unit = {
    // Select only columns that exist in PostgreSQL schema
    val pgDF = df.select(
      "thoi_gian", "ngay", "thang", "nam", "tuan", "gio",
      "ma_giao_dich", "chi_nhanh", "ma_hang", "ma_vach",
      "ten_hang", "thuong_hieu", "cap_1", "cap_2", "cap_3",
      "so_luong", "gia_ban_sp", "gia_von_sp", "loi_nhuan_sp",
      "doanh_thu", "giam_gia", "tong_gia_von", "loi_nhuan_gop",
      "ty_suat_loi_nhuan", "tong_loi_nhuan_hang_hoa"
    )
    
    pgDF.write
      .format("jdbc")
      .option("url", url)
      .option("dbtable", "staging_raw_transactions")
      .option("user", sys.env.getOrElse("POSTGRES_USER", "retail_user"))
      .option("password", sys.env.getOrElse("POSTGRES_PASSWORD", "retail_password"))
      .option("driver", "org.postgresql.Driver")
      .option("batchsize", "10000")
      .option("isolationLevel", "READ_COMMITTED")
      .mode("append")
      .save()
    
    logger.info(s"Written to PostgreSQL: staging_raw_transactions")
  }
}
