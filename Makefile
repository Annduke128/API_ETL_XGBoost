# Makefile cho Retail Data Pipeline
# Tất cả commands cần thiết để vận hành hệ thống

.PHONY: help up down restart logs ps clean \
        dbt dbt-test dbt-docs dbt-build dbt-build-staging dbt-build-marts dbt-build-full dbt-build-model \
        dbt-deps dbt-seed dbt-show dbt-show-model dbt-show-source dbt-preview dbt-list dbt-list-staging dbt-list-marts dbt-list-sources dbt-list-all \
        dbt-validate dbt-test-model dbt-compile dbt-docs-generate \
        sync-to-ch pipeline-full pipeline-quick app ch-tables ch-query data-summary check-services ml-summary \
        ml ml-train ml-predict ml-email-test ml-email-config psql clickhouse redis \
        process csv-import csv-reset \
        health health-postgres health-clickhouse health-redis health-superset \
        reset-db reset-all status

# ============================================================================
# HELP
# ============================================================================
help:
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║       Retail Data Pipeline - Available Commands                  ║"
	@echo "╠══════════════════════════════════════════════════════════════════╣"
	@echo "║  DOCKER COMPOSE                                                  ║"
	@echo "║    make up              - Start all services                     ║"
	@echo "║    make down            - Stop all services                      ║"
	@echo "║    make restart         - Restart all services                   ║"
	@echo "║    make logs            - View logs (follow mode)                ║"
	@echo "║    make ps              - List running containers                ║"
	@echo "║    make status          - Check all services status              ║"
	@echo "║                                                                  ║"
	@echo "║  HEALTH CHECK                                                    ║"
	@echo "║    make health          - Check all services health              ║"
	@echo "║    make health-postgres - Check PostgreSQL                       ║"
	@echo "║    make health-clickhouse Check ClickHouse                       ║"
	@echo "║    make health-redis    - Check Redis                            ║"
	@echo "║    make health-superset - Check Superset                         ║"
	@echo "║                                                                  ║"
	@echo "║  CSV PROCESSING                                                  ║"
	@echo "║    make process         - Process CSV files in csv_input/        ║"
	@echo "║    make csv-import      - Import CSV files to PostgreSQL         ║"
	@echo "║    make csv-reset       - Clear processed/error folders          ║"
	@echo "║                                                                  ║"
	@echo "║  DATA CHECK                                                      ║"
	@echo "║    make data-summary    - Show data counts before training       ║"
	@echo "║    make check-services  - Verify all services are running        ║"
	@echo "║                                                                  ║"
	@echo "║  DBT PIPELINE (Option C: Batch Sync)                             ║"
	@echo "║    make sync-to-ch      - Step 1: PG → CH Staging                ║"
	@echo "║    make dbt-build       - Step 2: Build ALL models + tests       ║"
	@echo "║    make pipeline-full   - Full: CSV + Sync + DBT                 ║"
	@echo "║    make app             - 🚀 Run EVERYTHING (Pipeline + ML + Email) ║"
	@echo "║                                                                  ║"
	@echo "║  DBT BEST PRACTICES (Always use --select)                        ║"
	@echo "║    make dbt-list-sources- List available sources                 ║"
	@echo "║    make dbt-list-staging- List staging models                    ║"
	@echo "║    make dbt-list-marts  - List marts models                      ║"
	@echo "║    make dbt-show-source SOURCE=x - Preview source data           ║"
	@echo "║    make dbt-preview MODEL=x - Preview model output               ║"
	@echo "║    make dbt-validate SELECT=x - Validate selection               ║"
	@echo "║                                                                  ║"
	@echo "║  DBT BUILD (with tests) - RECOMMENDED                            ║"
	@echo "║    make dbt-seed           - Load seeds (store_types, etc.)      ║"
	@echo "║    make dbt-build-staging  - Build staging only                  ║"
	@echo "║    make dbt-build-marts    - Build marts only                    ║"
	@echo "║    make dbt-build-model MODEL=x - Build specific model           ║"
	@echo "║    make dbt-build          - Build all (staging+marts)           ║"
	@echo "║    make dbt-build-full     - Full refresh rebuild                ║"
	@echo "║                                                                  ║"
	@echo "║  DBT TEST & COMPILE                                              ║"
	@echo "║    make dbt-test           - Run all tests                       ║"
	@echo "║    make dbt-test-model MODEL=x - Test specific model             ║"
	@echo "║    make dbt-compile        - Check syntax (no run)               ║"
	@echo "║                                                                  ║"
	@echo "║  DBT DOCUMENTATION                                               ║"
	@echo "║    make dbt-docs           - Generate & serve docs               ║"
	@echo "║    make dbt-docs-generate  - Generate docs only                  ║"
	@echo "║                                                                  ║"
	@echo "║  CLICKHOUSE                                                      ║"
	@echo "║    make ch-tables       - List tables                            ║"
	@echo "║    make ch-query        - Run SQL query                          ║"
	@echo "║                                                                  ║"
	@echo "║  ML (Machine Learning)                                           ║"
	@echo "║    make ml              - Train ML (Optuna 50 trials)            ║"
	@echo "║    make ml-all          - Train + Predict + Email                ║"
	@echo "║    make ml-train-force  - Alias for ml-all                       ║"
	@echo "║    make ml-check-data   - Check data/training status             ║"
	@echo "║    make ml-train        - Train với Optuna tuning                ║"
	@echo "║    make ml-train-fast   - Train nhanh (no tuning)                ║"
	@echo "║    make ml-train-optimal- Train tối ưu (100 trials)              ║"
	@echo "║    make ml-train-predict- Train + Generate forecasts             ║"
	@echo "║    make ml-predict      - Generate predictions (use old model)   ║"
	@echo "║                                                                  ║"
	@echo "║  EMAIL NOTIFICATIONS                                             ║"
	@echo "║    make ml-email-config - Xem hướng dẫn cấu hình email           ║"
	@echo "║    make ml-email-test   - Kiểm tra cấu hình email                ║"
	@echo "║    make ml-email-send-test - Gửi email test                      ║"
	@echo "║                                                                  ║"
	@echo "║  DATABASE CLI                                                    ║"
	@echo "║    make psql            - Connect to PostgreSQL                  ║"
	@echo "║    make clickhouse      - Connect to ClickHouse                  ║"
	@echo "║    make redis           - Connect to Redis CLI                   ║"
	@echo "║                                                                  ║"
	@echo "║  MAINTENANCE                                                     ║"
	@echo "║    make reset-db        - Reset database (keep CSV files)        ║"
	@echo "║    make reset-all       - Full reset (⚠️  destroys all data)     ║"
	@echo "║    make clean           - Clean Docker cache and volumes         ║"
	@echo "╚══════════════════════════════════════════════════════════════════╝"

# ============================================================================
# DOCKER COMPOSE COMMANDS
# ============================================================================

# Khởi động tất cả services
up:
	@echo "🚀 Starting all services..."
	docker-compose up -d postgres clickhouse redis
	@sleep 30
	docker-compose up -d airflow-init airflow-webserver airflow-scheduler
	docker-compose up -d superset-init superset-web
	@echo "⏳ Waiting for services to be healthy (60s)..."
	@sleep 60
	@echo "✅ All services started!"
	@docker-compose ps

# Dừng tất cả services
down:
	@echo "🛑 Stopping all services..."
	docker-compose down

# Restart services
restart:
	@echo "🔄 Restarting services..."
	docker-compose restart

# Xem logs
logs:
	docker-compose logs -f

# Liệt kê containers
ps:
	docker-compose ps

# Kiểm tra status
status:
	@echo "📊 Services Status:"
	@docker-compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# ============================================================================
# HEALTH CHECK
# ============================================================================

health: health-postgres health-clickhouse health-redis health-superset

health-postgres:
	@echo "🔍 Checking PostgreSQL..."
	@docker-compose exec -T postgres pg_isready -U retail_user -d retail_db && echo "✅ PostgreSQL is healthy" || echo "❌ PostgreSQL failed"

health-clickhouse:
	@echo "🔍 Checking ClickHouse..."
	@docker-compose exec -T clickhouse clickhouse-client -q "SELECT 'OK'" && echo "✅ ClickHouse is healthy" || echo "❌ ClickHouse failed"

health-redis:
	@echo "🔍 Checking Redis..."
	@docker-compose exec -T redis redis-cli ping && echo "✅ Redis is healthy" || echo "❌ Redis failed"

health-superset:
	@echo "🔍 Checking Superset..."
	@curl -s -o /dev/null -w "%{http_code}" http://localhost:8088/health | grep -q "200" && echo "✅ Superset is healthy" || echo "❌ Superset failed"

# ============================================================================
# CSV PROCESSING
# ============================================================================

# Xử lý CSV một lần
process: csv-import

# Trigger file import manually (chạy 1 lần) - Hỗ trợ CSV và Excel
csv-import:
	@echo "📁 Processing files (CSV & Excel)..."
	docker-compose --profile sync run --rm sync-tool python auto_process_files.py

# Xóa dữ liệu processed/error
csv-reset:
	@echo "🧹 Resetting CSV folders..."
	@docker run --rm -v "$(PWD)/csv_input:/csv" alpine sh -c \
		"rm -rf /csv/processed/* /csv/error/* 2>/dev/null; echo 'Done'"

# ============================================================================
# DBT COMMANDS (ClickHouse Target - Optimized with Best Practices)
# ============================================================================

# Environment variables
DBT_ENV := -e CLICKHOUSE_HOST=clickhouse \
			-e CLICKHOUSE_PORT=8123 \
			-e CLICKHOUSE_USER=default \
			-e CLICKHOUSE_PASSWORD=clickhouse_password \
			-e CLICKHOUSE_DB=retail_dw \
			-e POSTGRES_HOST=postgres \
			-e POSTGRES_PORT=5432 \
			-e POSTGRES_USER=retail_user \
			-e POSTGRES_PASSWORD=retail_password \
			-e POSTGRES_DB=retail_db

# ============================================================================
# DBT COMMANDS (ClickHouse Target - Following dbt Best Practices)
# ============================================================================
# BEST PRACTICES from dbt skills:
# 1. ALWAYS use --select (never run full project without approval)
# 2. Use --quiet to reduce output noise
# 3. Use dbt show to preview data before building
# 4. Use dbt list to validate selection before running
# 5. Use --inline for arbitrary SQL queries
# 6. Push LIMIT early in CTEs to minimize scanning

# DBT environment variables
DBT_QUIET := --quiet
DBT_TARGET := --target clickhouse

# Combined flags for standard commands
# Note: --warn-error-options không có trong dbt 1.7.0, chỉ dùng --quiet
DBT_STD_FLAGS := $(DBT_QUIET) $(DBT_TARGET)

# Step 1: Sync từ PostgreSQL sang ClickHouse Staging
sync-to-ch:
	@echo "🔄 Sync PostgreSQL → ClickHouse Staging..."
	docker-compose --profile sync run --rm sync-tool python sync_to_clickhouse.py

# Step 2: Install dependencies (no --quiet to see progress)
dbt-deps:
	@echo "📦 Installing DBT dependencies..."
	docker-compose run --rm $(DBT_ENV) dbt dbt deps $(DBT_TARGET)

# Load seeds (store_types, etc.) - REQUIRED before building models
dbt-seed: dbt-deps
	@echo "🌱 Loading DBT seeds..."
	docker-compose run --rm $(DBT_ENV) dbt dbt seed $(DBT_TARGET)
	@echo "✅ Seeds loaded!"

# ============================================================================
# DATA DISCOVERY & VALIDATION (Run these FIRST before building)
# ============================================================================

# List all sources to understand available data
dbt-list-sources:
	@echo "📋 Listing all SOURCES..."
	docker-compose run --rm $(DBT_ENV) dbt dbt list --select source:* $(DBT_TARGET)

# List staging models
dbt-list-staging:
	@echo "📋 Listing STAGING models..."
	docker-compose run --rm $(DBT_ENV) dbt dbt list --select staging $(DBT_TARGET)

# List marts models  
dbt-list-marts:
	@echo "📋 Listing MARTS models..."
	docker-compose run --rm $(DBT_ENV) dbt dbt list --select marts $(DBT_TARGET)

# List all models with JSON output for inspection
dbt-list-all:
	@echo "📋 Listing ALL models..."
	docker-compose run --rm $(DBT_ENV) dbt dbt list --select +staging,+marts $(DBT_TARGET)

# Preview source data (Step 1 of data discovery)
dbt-show-source:
	@echo "Usage: make dbt-show-source SOURCE=staging_products LIMIT=10"
	docker-compose run --rm $(DBT_ENV) dbt dbt show \
		--inline "SELECT * FROM {{ source('retail_source', '$(or $(SOURCE),staging_products)') }} LIMIT $(or $(LIMIT),10)" \
		$(DBT_TARGET)

# Preview model output before building
dbt-preview:
	@echo "Usage: make dbt-preview MODEL=stg_products LIMIT=10"
	docker-compose run --rm $(DBT_ENV) dbt dbt show \
		--select $(or $(MODEL),stg_products) \
		--limit $(or $(LIMIT),10) \
		$(DBT_TARGET)

# Validate selection before building (dry run)
dbt-validate:
	@echo "Usage: make dbt-validate SELECT=staging"
	@echo "🔍 Validating selection: $(or $(SELECT),staging)"
	docker-compose run --rm $(DBT_ENV) dbt dbt list \
		--select $(or $(SELECT),staging) \
		--resource-type model \
		$(DBT_TARGET)

# ============================================================================
# DBT BUILD COMMANDS (ALWAYS use --select)
# ============================================================================

# Build staging models only
dbt-build-staging: dbt-seed
	@echo "🔧 Building STAGING models (with tests)..."
	docker-compose run --rm $(DBT_ENV) dbt dbt build \
		$(DBT_STD_FLAGS) \
		--select staging
	@echo "✅ Staging build completed!"

# Build marts models only  
dbt-build-marts: dbt-seed
	@echo "🔧 Building MARTS models (with tests)..."
	docker-compose run --rm $(DBT_ENV) dbt dbt build \
		$(DBT_STD_FLAGS) \
		--select marts
	@echo "✅ Marts build completed!"

# Build specific model and its dependencies
dbt-build-model:
	@echo "Usage: make dbt-build-model MODEL=dim_product"
	@echo "🔧 Building model: $(MODEL) (+dependencies)"
	docker-compose run --rm $(DBT_ENV) dbt dbt build \
		$(DBT_STD_FLAGS) \
		--select +$(MODEL)

# Build all models (explicitly select staging+intermediate+marts, NEVER run without --select)
dbt-build: dbt-seed
	@echo "🔧 Building ALL models (staging + intermediate + marts)..."
	docker-compose run --rm $(DBT_ENV) dbt dbt build \
		$(DBT_STD_FLAGS) \
		--select staging,intermediate,marts
	@echo "✅ Full DBT build completed!"

# Full refresh rebuild (use with caution - explicit selection)
dbt-build-full: dbt-seed
	@echo "🔄 Full refresh build..."
	docker-compose run --rm $(DBT_ENV) dbt dbt build \
		$(DBT_STD_FLAGS) \
		--select staging,marts \
		--full-refresh
	@echo "✅ Full refresh completed!"

# ============================================================================
# TESTING & COMPILATION
# ============================================================================

# Test specific model
dbt-test-model:
	@echo "Usage: make dbt-test-model MODEL=dim_product"
	@echo "🧪 Testing model: $(MODEL)"
	docker-compose run --rm $(DBT_ENV) dbt dbt test \
		$(DBT_STD_FLAGS) \
		--select $(MODEL)

# Test all models
dbt-test:
	@echo "🧪 Running all tests..."
	docker-compose run --rm $(DBT_ENV) dbt dbt test \
		$(DBT_STD_FLAGS) \
		--select staging,marts

# Compile models (syntax check without running)
dbt-compile:
	@echo "🔍 Compiling models (syntax check)..."
	docker-compose run --rm $(DBT_ENV) dbt dbt compile \
		$(DBT_STD_FLAGS) \
		--select staging,marts

# ============================================================================
# DOCUMENTATION
# ============================================================================

# Generate và serve docs
dbt-docs:
	@echo "📚 Generating DBT docs..."
	docker-compose run --rm $(DBT_ENV) dbt dbt docs generate $(DBT_TARGET)
	@echo "📖 Starting docs server at http://localhost:8080"
	docker-compose run --rm $(DBT_ENV) -p 8080:8080 dbt dbt docs serve --host 0.0.0.0 --port 8080 $(DBT_TARGET)

# Generate docs only
dbt-docs-generate:
	@echo "📚 Generating DBT docs..."
	docker-compose run --rm $(DBT_ENV) dbt dbt docs generate $(DBT_TARGET)

# ============================================================================
# BATCH SYNC PIPELINE (Option C Architecture)
# ============================================================================
# Data Flow: CSV → PostgreSQL (Raw) → ClickHouse (Staging) → DBT (Marts)
#
# Step 1: csv-import     - Import CSV files to PostgreSQL (with deduplication)
# Step 2: sync-to-ch     - Sync PostgreSQL → ClickHouse Staging tables
# Step 3: dbt-build      - Transform Staging → Marts (dim_*, fct_*)

# Full pipeline: CSV → PostgreSQL → ClickHouse → DBT Marts
pipeline-full: csv-import sync-to-ch dbt-build
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║     ✅ BATCH SYNC PIPELINE COMPLETED SUCCESSFULLY            ║"
	@echo "╠══════════════════════════════════════════════════════════════╣"
	@echo "║  Data Flow:                                                  ║"
	@echo "║    CSV Files → PostgreSQL → ClickHouse Staging → DBT Marts   ║"
	@echo "╠══════════════════════════════════════════════════════════════╣"
	@echo "║  Next steps:                                                 ║"
	@echo "║    make ch-tables      - View all tables in ClickHouse       ║"
	@echo "║    make dbt-docs       - Generate and view DBT docs          ║"
	@echo "║    make ml-train       - Run ML training pipeline            ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"

# Quick pipeline (skip CSV import, data already in PostgreSQL)
# Use this when: Raw data already imported, just need to rebuild marts
pipeline-quick: sync-to-ch dbt-build
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║     ✅ QUICK PIPELINE COMPLETED                              ║"
	@echo "╠══════════════════════════════════════════════════════════════╣"
	@echo "║  Data Flow: PostgreSQL → ClickHouse → DBT Marts              ║"
	@echo "║  (Skipped: CSV import - assuming data exists in PostgreSQL)  ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"

# ============================================================================
# FULL APPLICATION (Data Pipeline + ML)
# ============================================================================
# Run everything: CSV → PostgreSQL → ClickHouse → DBT Marts → ML Training
# This is the ULTIMATE command to run the entire system end-to-end
#
# ⚠️  IMPORTANT: ML training requires sufficient historical data (multiple days)
#    If you only have 1 day of data, ML will skip or use fallback models

app: check-services pipeline-full ml-summary
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════════╗"
	@echo "║                                                                      ║"
	@echo "║          🎉 RETAIL DATA PIPELINE APPLICATION COMPLETE! 🎉             ║"
	@echo "║                                                                      ║"
	@echo "╠══════════════════════════════════════════════════════════════════════╣"
	@echo "║                                                                      ║"
	@echo "║  ✅ All stages completed:                                            ║"
	@echo "║                                                                      ║"
	@echo "║     1. 📁 CSV Import        → PostgreSQL                             ║"
	@echo "║     2. 🔄 Sync              → ClickHouse Staging                     ║"
	@echo "║     3. 🏗️  DBT Build        → Marts (dim_*, fct_*)                    ║"
	@echo "║     4. 🤖 ML Training       → 3 Forecasting Models                   ║"
	@echo "║     5. 🔮 Predictions       → 7-day forecasts for all products       ║"
	@echo "║     6. 📧 Email Report      → Sent to configured recipients          ║"
	@echo "║                                                                      ║"
	@echo "╠══════════════════════════════════════════════════════════════════════╣"
	@echo "║                                                                      ║"
	@echo "║  📊 Access your data:                                                ║"
	@echo "║     • ClickHouse:     make clickhouse                                ║"
	@echo "║     • PostgreSQL:     make psql                                      ║"
	@echo "║     • DBT Docs:       make dbt-docs                                  ║"
	@echo "║     • View tables:    make ch-tables                                 ║"
	@echo "║                                                                      ║"
	@echo "║  🔮 ML & Forecasting:                                                ║"
	@echo "║     • Generate predictions:  make ml-predict                         ║"
	@echo "║     • Train models:          make ml-train                           ║"
	@echo "║     • Check data:            make data-summary                       ║"
	@echo "║                                                                      ║"
	@echo "╚══════════════════════════════════════════════════════════════════════╝"

# Check if services are running before starting
.PHONY: check-services
check-services:
	@echo "🔍 Checking services..."
	@docker-compose ps | grep -q "retail_postgres.*Up" || (echo "❌ PostgreSQL not running. Run: make up" && exit 1)
	@docker-compose ps | grep -q "retail_clickhouse.*Up" || (echo "❌ ClickHouse not running. Run: make up" && exit 1)
	@echo "✅ All services are running"

# Show data summary before ML training
data-summary:
	@echo ""
	@echo "📊 DATA SUMMARY"
	@echo "==============="
	@echo ""
	@echo "PostgreSQL (Raw Data):"
	@docker-compose exec -T postgres psql -U retail_user -d retail_db -c "SELECT 'transactions' as table_name, COUNT(*) as rows FROM transactions UNION ALL SELECT 'transaction_details', COUNT(*) FROM transaction_details UNION ALL SELECT 'products', COUNT(*) FROM products;" 2>/dev/null || echo "   ⚠️  Cannot connect to PostgreSQL"
	@echo ""
	@echo "ClickHouse (Staging & Marts):"
	@docker-compose exec -T clickhouse clickhouse-client -q "SELECT 'staging_transactions' as table, count() FROM retail_dw.staging_transactions UNION ALL SELECT 'staging_products', count() FROM retail_dw.staging_products UNION ALL SELECT 'fct_daily_sales', count() FROM retail_dw.fct_daily_sales UNION ALL SELECT 'dim_product', count() FROM retail_dw.dim_product;" 2>/dev/null || echo "   ⚠️  Cannot connect to ClickHouse"
	@echo ""
	@echo "Date Range:"
	@docker-compose exec -T clickhouse clickhouse-client -q "SELECT COUNT(DISTINCT transaction_date) as unique_days, MIN(transaction_date) as min_date, MAX(transaction_date) as max_date FROM retail_dw.fct_daily_sales;" 2>/dev/null || echo "   ⚠️  No data in fct_daily_sales"
	@echo ""

# ML Summary (runs ML training + predictions + email report)
ml-summary: data-summary ml-all
	@echo ""
	@echo "📈 ML Training & Prediction Summary"
	@echo "===================================="

# Kiểm tra tables trong ClickHouse
ch-tables:
	@echo "📊 Tables in ClickHouse:"
	@docker-compose exec -T clickhouse clickhouse-client -q "SHOW TABLES FROM retail_dw"

# Query ClickHouse trực tiếp
ch-query:
	@echo "Usage: make ch-query SQL='SELECT * FROM dim_product LIMIT 5'"
	@docker-compose exec -T clickhouse clickhouse-client -q "$(SQL)"

# Legacy commands (backward compatibility)
dbt: dbt-build
dbt-test: dbt-build

# ============================================================================
# ML COMMANDS
# ============================================================================

# Train ML models với Optuna tuning (default)
ml: ml-train

ml-train:
	@echo "🤖 Training ML models với Optuna tuning..."
	docker-compose --profile ml run --rm ml-pipeline python train_models.py --trials 50

# Train nhanh (không tuning)
ml-train-fast:
	@echo "⚡ Training ML models (no tuning)..."
	docker-compose --profile ml run --rm ml-pipeline python train_models.py --no-tuning

# Train với nhiều trials (tối ưu hơn, lâu hơn)
ml-train-optimal:
	@echo "🎯 Training ML models với 100 trials..."
	docker-compose --profile ml run --rm ml-pipeline python train_models.py --trials 100

# Train + Predict
ml-train-predict:
	@echo "🤖 Training + Generating forecasts..."
	docker-compose --profile ml run --rm ml-pipeline python train_models.py --trials 50 --predict

# Train + Predict không gửi email
ml-train-predict-no-email:
	@echo "🤖 Training + Generating forecasts (no email)..."
	docker-compose --profile ml run --rm ml-pipeline python train_models.py --trials 50 --predict --no-email

# Generate predictions từ model đã train
ml-predict:
	@echo "📈 Generating predictions..."
	docker-compose --profile ml run --rm ml-pipeline python -c \
		"from xgboost_forecast import SalesForecaster; f = SalesForecaster(); p = f.predict_next_week(); f.save_forecasts(p)"

# Generate comprehensive report từ models đã train
ml-report:
	@echo "📊 Generating comprehensive forecast report..."
	docker-compose --profile ml run --rm ml-pipeline python /app/xgboost_forecast.py --mode report

# Train + Generate comprehensive report
ml-all:
	@echo "🚀 Training + Predicting + Sending email report..."
	@echo "   • Loading historical data from ClickHouse"
	@echo "   • Training 3 models with Optuna tuning"
	@echo "   • Generating 7-day forecasts for all products"
	@echo "   • Sending comprehensive report via email"
	docker-compose --profile ml run --rm ml-pipeline python /app/xgboost_forecast.py --mode all --trials 30

# Alias for ml-all (để tương thích)
ml-train-force:
	@echo "🚀 FORCE TRAINING..."
	@make ml-all

# Check data status
ml-check-data:
	@echo "🔍 Checking data status..."
	docker-compose --profile ml run --rm ml-pipeline python -c \
		"from xgboost_forecast import SalesForecaster; f=SalesForecaster(); d=f.get_latest_data_date(); t=f.get_last_training_date(); print(f'Latest data: {d}\\nLast training: {t}')"

# Test email configuration
ml-test-email:
	@echo "📧 Testing email configuration..."
	docker-compose --profile ml run --rm ml-pipeline python /app/email_notifier.py --validate

# ============================================================================
# DATABASE CLI
# ============================================================================

# PostgreSQL CLI
psql:
	docker-compose exec postgres psql -U retail_user -d retail_db

# ClickHouse CLI
clickhouse:
	docker-compose exec clickhouse clickhouse-client

# Redis CLI
redis:
	docker-compose exec redis redis-cli

# ============================================================================
# MAINTENANCE
# ============================================================================

# Reset database (xóa dữ liệu nhưng giữ files)
reset-db:
	@echo "⚠️  Resetting databases..."
	@echo "  - PostgreSQL (raw data)..."
	@docker-compose exec -T postgres psql -U retail_user -d retail_db -c \
		"TRUNCATE TABLE transaction_details, transactions, products, branches, ml_forecasts RESTART IDENTITY CASCADE;" 2>/dev/null || true
	@echo "  - ClickHouse (staging + marts)..."
	@docker-compose exec -T clickhouse clickhouse-client -q "SHOW TABLES FROM retail_dw" 2>/dev/null | xargs -I {} docker-compose exec -T clickhouse clickhouse-client -q "DROP TABLE IF EXISTS retail_dw.{}" 2>/dev/null || true
	@docker-compose exec redis redis-cli FLUSHDB 2>/dev/null || true
	@echo "✅ Databases reset!"

# Full reset (⚠️ destructive)
reset-all: down
	@echo "⚠️  Full reset - destroying all data..."
	docker-compose down -v
	docker system prune -f
	@echo "✅ System fully reset! Run 'make up' to start fresh."

# Clean Docker cache
clean:
	@echo "🧹 Cleaning Docker cache..."
	docker system prune -f
	docker volume prune -f

# View disk usage
disk:
	docker system df

# ============================================================================
# EMAIL NOTIFICATION COMMANDS
# ============================================================================

# Kiểm tra cấu hình email
ml-email-test:
	@echo "📧 Testing email configuration..."
	docker-compose --profile ml run --rm ml-pipeline python test_email.py

# Gửi email test
ml-email-send-test:
	@echo "📤 Sending test email..."
	docker-compose --profile ml run --rm ml-pipeline python test_email.py --send-test

# Mở file cấu hình email để chỉnh sửa
ml-email-config:
	@echo "📝 Opening email configuration file..."
	@echo "File location: ml_pipeline/email_config.yaml"
	@echo ""
	@echo "📋 Hướng dẫn cấu hình:"
	@echo "   1. Thay đổi 'primary' email thành email của bạn"
	@echo "   2. Thêm email phụ trong 'additional' (tùy chọn)"
	@echo "   3. Bật/tắt các loại thông báo trong 'notifications'"
	@echo "   4. Kiểm tra cấu hình SMTP (server, port)"
	@echo ""
	@echo "🔐 Thiết lập Gmail App Password:"
	@echo "   1. Bật 2-Factor Authentication trong Google Account"
	@echo "   2. Truy cập: https://myaccount.google.com/apppasswords"
	@echo "   3. Tạo App Password cho 'Mail' > 'Other (Custom name)'"
	@echo "   4. Copy 16 ký tự vào .env hoặc biến môi trường EMAIL_PASSWORD"
	@echo ""
	@echo "✅ Sau khi cấu hình xong, test với: make ml-email-send-test"
