# Makefile cho Retail Data Pipeline - Docker Operations
# Tất cả commands liên quan đến Docker deployment
# 
# Usage: make [command]
#        make up          - Khởi động services
#        make down        - Dừng services
#        make build       - Build images
#        make push        - Push lên registry

.PHONY: help up down restart logs ps status \
        health health-postgres health-clickhouse health-redis health-superset \
        build push pull \
        dbt dbt-test dbt-docs dbt-build dbt-build-staging dbt-build-marts dbt-build-full \
        dbt-deps dbt-seed dbt-list dbt-list-staging dbt-list-marts dbt-list-sources \
        dbt-preview dbt-show-source dbt-show-model dbt-validate \
        sync-to-ch pipeline-full pipeline-quick app app-legacy smart smart-process smart-dry-run \
        ml ml-train ml-predict ml-all ml-train-fast ml-train-optimal \
        spark spark-up spark-down spark-etl spark-status \
        psql clickhouse redis \
        reset-db reset-all clean disk

# ============================================================================
# HELP
# ============================================================================
help:
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║       Retail Data Pipeline - Docker Commands                     ║"
	@echo "╠══════════════════════════════════════════════════════════════════╣"
	@echo "║  DOCKER COMPOSE                                                  ║"
	@echo "║    make up              - Start all infrastructure services      ║"
	@echo "║    make up ml           - Start with ML Pipeline                 ║"
	@echo "║    make up sync         - Start with Sync Tool                   ║"
	@echo "║    make up all          - Start ALL services                     ║"
	@echo "║    make down            - Stop all services                      ║"
	@echo "║    make down-v          - Stop and remove volumes                ║"
	@echo "║    make restart         - Restart all services                   ║"
	@echo "║    make logs            - View logs (follow mode)                ║"
	@echo "║    make ps              - List running containers                ║"
	@echo "║    make status          - Check all services status              ║"
	@echo "║                                                                  ║"
	@echo "║  DOCKER BUILD                                                    ║"
	@echo "║    make build           - Build all custom images                ║"
	@echo "║    make build SERVICE=x - Build specific service image           ║"
	@echo "║                                                                  ║"
	@echo "║  HEALTH CHECK                                                    ║"
	@echo "║    make health          - Check all services health              ║"
	@echo "║    make health-postgres - Check PostgreSQL                       ║"
	@echo "║    make health-clickhouse Check ClickHouse                       ║"
	@echo "║    make health-redis    - Check Redis                            ║"
	@echo "║    make health-superset - Check Superset                         ║"
	@echo "║                                                                  ║"
	@echo "║  DATA PIPELINE                                                   ║"
	@echo "║    make sync-to-ch      - Sync PostgreSQL → ClickHouse           ║"
	@echo "║    make dbt-build       - Build ALL DBT models                   ║"
	@echo "║    make pipeline-full   - Full: Sync + DBT                       ║"
	@echo "║                                                                  ║"
	@echo "║  DBT COMMANDS                                                    ║"
	@echo "║    make dbt-deps        - Install dependencies                   ║"
	@echo "║    make dbt-seed        - Load seeds                             ║"
	@echo "║    make dbt-list-staging- List staging models                    ║"
	@echo "║    make dbt-list-marts  - List marts models                      ║"
	@echo "║    make dbt-preview MODEL=x - Preview model                      ║"
	@echo "║    make dbt-build-model MODEL=x - Build specific model           ║"
	@echo "║    make dbt-docs        - Generate and serve docs                ║"
	@echo "║                                                                  ║"
	@echo "║  ML PIPELINE                                                     ║"
	@echo "║    make ml              - Train ML models (Optuna)               ║"
	@echo "║    make ml-fast         - Train without tuning                   ║"
	@echo "║    make ml-optimal      - Train with 100 trials                  ║"
	@echo "║    make ml-all          - Train + Predict + Email                ║"
	@echo "║    make ml-predict      - Generate predictions only              ║"
	@echo "║                                                                  ║"
	@echo "║  SMART PROCESSOR (Auto-detect)                                   ║"
	@echo "║    make smart           - Auto-detect & process all files        ║"
	@echo "║    make smart-dry-run   - Preview processing plan                ║"
	@echo "║    make smart-process   - Process: Products→Inventory→Sales      ║"
	@echo "║                                                                  ║"
	@echo "║  SPARK ETL (Hybrid)                                              ║"
	@echo "║    make spark-up        - Start Spark cluster                    ║"
	@echo "║    make spark-etl       - Run Spark ETL pipeline                 ║"
	@echo "║    make spark-status    - Check Spark status                     ║"
	@echo "║    make spark-down      - Stop Spark cluster                     ║"
	@echo "║                                                                  ║"
	@echo "║  INVENTORY (Local Test)                                          ║"
	@echo "║    make inventory-import   - Import Excel tồn kho                ║"
	@echo "║    make inventory-check    - Kiểm tra dữ liệu tồn kho            ║"
	@echo "║    make inventory-products-check - Check matching với products   ║"
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
	@echo "║    make disk            - Show Docker disk usage                 ║"
	@echo "╚══════════════════════════════════════════════════════════════════╝"

# ============================================================================
# DOCKER COMPOSE COMMANDS
# ============================================================================

COMPOSE_FILE := docker-compose.yml
ENV_FILE := .env

# Khởi động infrastructure cơ bản
up:
	@if [ ! -f $(ENV_FILE) ]; then \
		if [ -f ../.env ]; then \
			echo "⚠️  Copying .env from parent directory..."; \
			cp ../.env .env; \
		elif [ -f .env.example ]; then \
			echo "⚠️  Creating .env from .env.example..."; \
			cp .env.example .env; \
		else \
			echo "⚠️  Warning: No .env file found. Using default values..."; \
		fi \
	fi
	@echo "🚀 Starting infrastructure services..."
	docker-compose -f $(COMPOSE_FILE) up -d redis postgres clickhouse
	@sleep 5
	@echo "⏳ Waiting for databases to be ready..."
	@sleep 10
	@echo "🚀 Starting Airflow..."
	docker-compose -f $(COMPOSE_FILE) up -d airflow-postgres airflow-init airflow-webserver airflow-scheduler
	@echo "🚀 Starting Superset..."
	docker-compose -f $(COMPOSE_FILE) up -d superset-db superset-cache superset-init superset-web
	@echo "✅ Infrastructure started!"
	@echo ""
	@echo "Access points:"
	@echo "  - Airflow:    http://localhost:8085 (admin/admin)"
	@echo "  - Superset:   http://localhost:8088 (admin/admin)"
	@echo "  - ClickHouse: localhost:8123"
	@echo "  - PostgreSQL: localhost:5432"
	@echo ""
	@echo "To start ML Pipeline:    make up ml"
	@echo "To start Sync Tool:      make up sync"

# Khởi động với ML Pipeline
up-ml:
	@make up
	@echo "🤖 Starting ML Pipeline..."
	docker-compose -f $(COMPOSE_FILE) --profile ml up -d ml-pipeline

# Khởi động với Sync Tool
up-sync:
	@make up
	@echo "🔄 Starting Sync Tool..."
	docker-compose -f $(COMPOSE_FILE) --profile sync up -d sync-tool

# Khởi động Spark cluster
up-spark:
	@make up
	@echo "🔥 Starting Spark cluster..."
	docker-compose -f $(COMPOSE_FILE) --profile spark up -d spark-master spark-worker
	@sleep 10
	@echo "✅ Spark cluster started!"
	@echo "   Spark UI: http://localhost:8090"

# Khởi động tất cả services
up-all:
	@if [ ! -f $(ENV_FILE) ]; then \
		if [ -f ../.env ]; then \
			echo "⚠️  Copying .env from parent directory..."; \
			cp ../.env .env; \
		elif [ -f .env.example ]; then \
			echo "⚠️  Creating .env from .env.example..."; \
			cp .env.example .env; \
		else \
			echo "⚠️  Warning: No .env file found. Using default values..."; \
		fi \
	fi
	@echo "🚀 Starting ALL services..."
	docker-compose -f $(COMPOSE_FILE) --profile ml --profile sync up -d
	@echo "✅ All services started!"

# Dừng tất cả services
down:
	@echo "🛑 Stopping services..."
	docker-compose -f $(COMPOSE_FILE) --profile ml --profile sync down

# Dừng và xóa volumes
down-v:
	@echo "🛑 Stopping services and removing volumes..."
	docker-compose -f $(COMPOSE_FILE) --profile ml --profile sync down -v

# Restart services
restart:
	@echo "🔄 Restarting services..."
	docker-compose -f $(COMPOSE_FILE) restart

# Xem logs
logs:
	docker-compose -f $(COMPOSE_FILE) logs -f

# Xem logs của service cụ thể
logs-%:
	docker-compose -f $(COMPOSE_FILE) logs -f $*

# Liệt kê containers
ps:
	docker-compose -f $(COMPOSE_FILE) ps

# Kiểm tra status
status:
	@echo "📊 Services Status:"
	@docker-compose -f $(COMPOSE_FILE) ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# ============================================================================
# DOCKER BUILD
# ============================================================================

# Build tất cả custom images
build:
	@echo "🔨 Building custom images..."
	docker-compose -f $(COMPOSE_FILE) build dbt ml-pipeline sync-tool
	@echo "✅ Build completed!"
	@echo ""
	@echo "Images built:"
	@echo "  - retail-dbt:latest"
	@echo "  - retail-ml-pipeline:latest"
	@echo "  - retail-sync-tool:latest"

# Build specific service
build-service:
	@if [ -z "$(SERVICE)" ]; then \
		echo "❌ Please specify SERVICE=name"; \
		echo "Example: make build-service SERVICE=ml-pipeline"; \
		exit 1; \
	fi
	@echo "🔨 Building image for $(SERVICE)..."
	docker-compose -f $(COMPOSE_FILE) build $(SERVICE)

# ============================================================================
# HEALTH CHECK
# ============================================================================

health: health-postgres health-clickhouse health-redis

health-postgres:
	@echo "🔍 Checking PostgreSQL..."
	@docker-compose -f $(COMPOSE_FILE) exec -T postgres pg_isready -U retail_user -d retail_db && echo "✅ PostgreSQL is healthy" || echo "❌ PostgreSQL failed"

health-clickhouse:
	@echo "🔍 Checking ClickHouse..."
	@docker-compose -f $(COMPOSE_FILE) exec -T clickhouse wget -q --spider http://127.0.0.1:8123/ping && echo "✅ ClickHouse is healthy" || echo "❌ ClickHouse failed"

health-redis:
	@echo "🔍 Checking Redis..."
	@docker-compose -f $(COMPOSE_FILE) exec -T redis redis-cli ping && echo "✅ Redis is healthy" || echo "❌ Redis failed"

health-superset:
	@echo "🔍 Checking Superset..."
	@curl -s -o /dev/null -w "%{http_code}" http://localhost:8088/api/v1/health | grep -q "200" && echo "✅ Superset is healthy" || echo "❌ Superset failed"

# ============================================================================
# ENVIRONMENT VARIABLES
# ============================================================================

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

DBT_TARGET := --target clickhouse

# ============================================================================
# DATA PIPELINE
# ============================================================================

# Sync từ PostgreSQL sang ClickHouse
sync-to-ch:
	@echo "🔄 Sync PostgreSQL → ClickHouse Staging..."
	docker-compose -f $(COMPOSE_FILE) --profile sync run --rm sync-tool python sync_to_clickhouse.py

# Full pipeline
pipeline-full: sync-to-ch dbt-build
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║     ✅ BATCH SYNC PIPELINE COMPLETED SUCCESSFULLY            ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"

# ============================================================================
# SMART PROCESSOR (Auto-detect by filename)
# ============================================================================

smart-process:
	@echo "🧠 Smart Processing: Auto-detecting files..."
	@echo "   Order: Products → Inventory → Sales → Promotions"
	docker-compose -f $(COMPOSE_FILE) --profile smart run --rm smart-processor \
		python smart_processor.py --input /csv_input --output /csv_output

smart-dry-run:
	@echo "🔍 Smart Dry-Run: Preview processing plan..."
	docker-compose -f $(COMPOSE_FILE) --profile smart run --rm smart-processor \
		python smart_processor.py --input /csv_input --output /csv_output --dry-run

smart: smart-process

# ============================================================================
# ONE-SHOT FULL PIPELINE COMMANDS
# ============================================================================

# 🚀 Smart full pipeline (Recommended)
app: smart-process sync-to-ch dbt-build ml-all
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════════╗"
	@echo "║              ✅ SMART APPLICATION COMPLETE! ✅                        ║"
	@echo "╠══════════════════════════════════════════════════════════════════════╣"
	@echo "║  ✅ All stages completed with Smart Processing:                      ║"
	@echo "║     1. 🧠 Smart Detection & Processing (Products→Inventory→Sales)    ║"
	@echo "║     2. 🔄 Sync to ClickHouse                                         ║"
	@echo "║     3. 🏗️  DBT Build                                                 ║"
	@echo "║     4. 🤖 ML Training & Prediction                                   ║"
	@echo "╚══════════════════════════════════════════════════════════════════════╝"

# 🔄 Legacy full pipeline
app-legacy: pipeline-full ml-all
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════════╗"
	@echo "║              ✅ LEGACY APPLICATION COMPLETE! ✅                       ║"
	@echo "╠══════════════════════════════════════════════════════════════════════╣"
	@echo "║  ✅ All stages completed:                                            ║"
	@echo "║     1. 📁 CSV Processing (Legacy)                                    ║"
	@echo "║     2. 🔄 Sync to ClickHouse                                         ║"
	@echo "║     3. 🏗️  DBT Build                                                 ║"
	@echo "║     4. 🤖 ML Training & Prediction                                   ║"
	@echo "╚══════════════════════════════════════════════════════════════════════╝"

# ============================================================================
# DBT COMMANDS
# ============================================================================

dbt-deps:
	@echo "📦 Installing DBT dependencies..."
	docker-compose -f $(COMPOSE_FILE) run --rm $(DBT_ENV) dbt dbt deps $(DBT_TARGET)

dbt-seed: dbt-deps
	@echo "🌱 Loading DBT seeds..."
	docker-compose -f $(COMPOSE_FILE) run --rm $(DBT_ENV) dbt dbt seed $(DBT_TARGET)

dbt-list-sources:
	@echo "📋 Listing all SOURCES..."
	docker-compose -f $(COMPOSE_FILE) run --rm $(DBT_ENV) dbt dbt list --select source:* $(DBT_TARGET)

dbt-list-staging:
	@echo "📋 Listing STAGING models..."
	docker-compose -f $(COMPOSE_FILE) run --rm $(DBT_ENV) dbt dbt list --select staging $(DBT_TARGET)

dbt-list-marts:
	@echo "📋 Listing MARTS models..."
	docker-compose -f $(COMPOSE_FILE) run --rm $(DBT_ENV) dbt dbt list --select marts $(DBT_TARGET)

dbt-show-source:
	@if [ -z "$(SOURCE)" ]; then \
		echo "Usage: make dbt-show-source SOURCE=staging_products [LIMIT=10]"; \
		exit 1; \
	fi
	@LIMIT=$(or $(LIMIT),10); \
	docker-compose -f $(COMPOSE_FILE) run --rm $(DBT_ENV) dbt dbt show \
		--inline "SELECT * FROM {{ source('retail_source', '$(SOURCE)') }} LIMIT $$LIMIT" \
		$(DBT_TARGET)

dbt-preview:
	@if [ -z "$(MODEL)" ]; then \
		echo "Usage: make dbt-preview MODEL=stg_products [LIMIT=10]"; \
		exit 1; \
	fi
	@LIMIT=$(or $(LIMIT),10); \
	docker-compose -f $(COMPOSE_FILE) run --rm $(DBT_ENV) dbt dbt show \
		--select $(MODEL) \
		--limit $$LIMIT \
		$(DBT_TARGET)

dbt-build-staging: dbt-seed
	@echo "🔧 Building STAGING models..."
	docker-compose -f $(COMPOSE_FILE) run --rm $(DBT_ENV) dbt dbt build \
		--select staging $(DBT_TARGET)

dbt-build-marts: dbt-seed
	@echo "🔧 Building MARTS models..."
	docker-compose -f $(COMPOSE_FILE) run --rm $(DBT_ENV) dbt dbt build \
		--select marts $(DBT_TARGET)

dbt-build: dbt-seed
	@echo "🔧 Building ALL models..."
	docker-compose -f $(COMPOSE_FILE) run --rm $(DBT_ENV) dbt dbt build \
		--select models/staging models/marts $(DBT_TARGET)

dbt-build-full: dbt-seed
	@echo "🔄 Full refresh build..."
	docker-compose -f $(COMPOSE_FILE) run --rm $(DBT_ENV) dbt dbt build \
		--select staging,marts --full-refresh $(DBT_TARGET)

dbt-build-model:
	@if [ -z "$(MODEL)" ]; then \
		echo "Usage: make dbt-build-model MODEL=dim_product"; \
		exit 1; \
	fi
	@echo "🔧 Building model: $(MODEL)"
	docker-compose -f $(COMPOSE_FILE) run --rm $(DBT_ENV) dbt dbt build \
		--select +$(MODEL) $(DBT_TARGET)

dbt-test:
	@echo "🧪 Running all tests..."
	docker-compose -f $(COMPOSE_FILE) run --rm $(DBT_ENV) dbt dbt test \
		--select staging,marts $(DBT_TARGET)

dbt-docs:
	@echo "📚 Generating DBT docs..."
	docker-compose -f $(COMPOSE_FILE) run --rm $(DBT_ENV) dbt dbt docs generate $(DBT_TARGET)
	@echo "📖 Starting docs server at http://localhost:8080"
	docker-compose -f $(COMPOSE_FILE) run --rm $(DBT_ENV) -p 8080:8080 dbt dbt docs serve --host 0.0.0.0 --port 8080 $(DBT_TARGET)

# ============================================================================
# ML PIPELINE
# ============================================================================

ml: ml-train

ml-train:
	@echo "🤖 Training ML models with Optuna tuning (50 trials)..."
	docker-compose -f $(COMPOSE_FILE) --profile ml run --rm ml-pipeline train_models.py --trials 50

ml-fast:
	@echo "⚡ Training ML models (no tuning)..."
	docker-compose -f $(COMPOSE_FILE) --profile ml run --rm ml-pipeline train_models.py --no-tuning

ml-optimal:
	@echo "🎯 Training ML models with 100 trials..."
	docker-compose -f $(COMPOSE_FILE) --profile ml run --rm ml-pipeline train_models.py --trials 100

ml-all:
	@echo "🚀 Training + Predicting + Email report..."
	docker-compose -f $(COMPOSE_FILE) --profile ml run --rm ml-pipeline xgboost_forecast.py --mode all --trials 30

ml-predict:
	@echo "📈 Generating predictions..."
	docker-compose -f $(COMPOSE_FILE) --profile ml run --rm ml-pipeline -c \
		"from xgboost_forecast import SalesForecaster; f = SalesForecaster(); p = f.predict_next_week(); f.save_forecasts(p)"

# ============================================================================
# SPARK ETL (Hybrid Architecture)
# ============================================================================

spark: spark-up

spark-up:
	@echo "🔥 Starting Spark cluster..."
	@make up
	@sleep 5
	docker-compose -f $(COMPOSE_FILE) --profile spark up -d spark-master spark-worker
	@sleep 10
	@echo "✅ Spark cluster started!"
	@echo "   Spark Master UI: http://localhost:8090"
	@echo "   Spark Master: spark://spark-master:7077"

spark-down:
	@echo "🛑 Stopping Spark cluster..."
	docker-compose -f $(COMPOSE_FILE) --profile spark --profile spark-etl down

spark-status:
	@echo "🔥 Spark Cluster Status"
	@echo "======================"
	@docker-compose -f $(COMPOSE_FILE) --profile spark ps
	@echo ""
	@echo "Spark UI: http://localhost:8090"

spark-logs:
	@echo "📜 Spark Master Logs:"
	@docker-compose -f $(COMPOSE_FILE) logs --tail=50 spark-master

# Run Spark ETL pipeline
spark-etl:
	@echo "⚡ Running Spark Hybrid ETL..."
	@echo "   Phase 1: Spark (Scala) - Heavy Lifting"
	@echo "   Phase 2: Python UDFs - Business Logic"
	@echo "   Phase 3: Sync to ClickHouse"
	docker-compose -f $(COMPOSE_FILE) --profile spark --profile spark-etl run --rm spark-etl
	@echo ""
	@echo "✅ Spark ETL completed!"

# Full pipeline with Spark
pipeline-spark: spark-etl dbt-build
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║     ✅ SPARK HYBRID PIPELINE COMPLETED SUCCESSFULLY          ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"

# ============================================================================
# INVENTORY IMPORT (Local Testing)
# ============================================================================

inventory-import:
	@echo "📦 Importing inventory from Excel..."
	docker-compose -f $(COMPOSE_FILE) --profile inventory run --rm inventory-import

inventory-check:
	@echo "🔍 Checking inventory data..."
	@docker-compose -f $(COMPOSE_FILE) exec -T postgres psql -U retail_user -d retail_db -c \
		"SELECT ngay_bao_cao, chi_nhanh, COUNT(*) as so_san_pham, SUM(ton_cuoi_ky) as tong_ton FROM inventory_transactions GROUP BY ngay_bao_cao, chi_nhanh;"

inventory-products-check:
	@echo "🔍 Checking inventory vs products matching..."
	@docker-compose -f $(COMPOSE_FILE) exec -T postgres psql -U retail_user -d retail_db -c \
		"SELECT COUNT(*) as total, SUM(CASE WHEN p.id IS NOT NULL THEN 1 ELSE 0 END) as matched FROM inventory_transactions i LEFT JOIN products p ON i.ma_vach = p.ma_vach;"

# ============================================================================
# DATABASE CLI
# ============================================================================

psql:
	docker-compose -f $(COMPOSE_FILE) exec postgres psql -U retail_user -d retail_db

clickhouse:
	docker-compose -f $(COMPOSE_FILE) exec clickhouse clickhouse-client

redis:
	docker-compose -f $(COMPOSE_FILE) exec redis redis-cli

# ============================================================================
# MAINTENANCE
# ============================================================================

reset-db:
	@echo "⚠️  Resetting databases..."
	@echo "  - PostgreSQL..."
	@docker-compose -f $(COMPOSE_FILE) exec -T postgres psql -U retail_user -d retail_db -c \
		"TRUNCATE TABLE transaction_details, transactions, products, branches RESTART IDENTITY CASCADE;" 2>/dev/null || true
	@echo "  - ClickHouse..."
	@docker-compose -f $(COMPOSE_FILE) exec -T clickhouse clickhouse-client -q \
		"SHOW TABLES FROM retail_dw" 2>/dev/null | xargs -I {} \
		docker-compose -f $(COMPOSE_FILE) exec -T clickhouse clickhouse-client -q \
		"TRUNCATE TABLE IF EXISTS retail_dw.{}" 2>/dev/null || true
	@echo "  - Redis..."
	@docker-compose -f $(COMPOSE_FILE) exec -T redis redis-cli FLUSHDB 2>/dev/null || true
	@echo "✅ Databases reset!"

reset-all: down
	@echo "⚠️  Full reset - destroying all data..."
	docker-compose -f $(COMPOSE_FILE) down -v
	docker system prune -f
	@echo "✅ System fully reset!"

clean:
	@echo "🧹 Cleaning Docker cache..."
	docker system prune -f
	docker volume prune -f

disk:
	@echo "💾 Docker disk usage:"
	docker system df
