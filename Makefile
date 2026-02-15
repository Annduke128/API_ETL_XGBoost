# Makefile cho Retail Data Pipeline
# Tất cả commands cần thiết để vận hành hệ thống

.PHONY: help up down restart logs ps clean dbt dbt-test dbt-docs \
        ml ml-train ml-predict ml-email-test ml-email-config psql clickhouse redis \
        process csv-import csv-watch csv-reset \
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
	@echo "║    make csv-import      - Import CSV manually                    ║"
	@echo "║    make csv-watch       - Start auto-watch mode                  ║"
	@echo "║    make csv-reset       - Clear processed/error folders          ║"
	@echo "║                                                                  ║"
	@echo "║  DBT (Data Transformation)                                       ║"
	@echo "║    make dbt             - Run all DBT models                     ║"
	@echo "║    make dbt-seed        - Load seed data                         ║"
	@echo "║    make dbt-test        - Run DBT tests                          ║"
	@echo "║    make dbt-docs        - Generate and serve DBT docs            ║"
	@echo "║                                                                  ║"
	@echo "║  ML (Machine Learning)                                           ║"
	@echo "║    make ml              - Train ML (Optuna 50 trials)            ║"
	@echo "║    make ml-train        - Train với Optuna tuning                ║"
	@echo "║    make ml-train-fast   - Train nhanh (no tuning)                ║"
	@echo "║    make ml-train-optimal- Train tối ưu (100 trials)              ║"
	@echo "║    make ml-train-predict- Train + Generate forecasts             ║"
	@echo "║    make ml-predict      - Generate predictions                   ║"
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

# Trigger CSV import manually (chạy 1 lần)
csv-import:
	@echo "📁 Processing CSV files..."
	docker-compose --profile watcher run --rm csv-watcher python auto_process_csv.py

# Chạy CSV import + DBT transform (giống Airflow DAG)
csv-process-full: csv-import dbt
	@echo "✅ CSV processing and DBT transform completed"

# Xóa dữ liệu processed/error
csv-reset:
	@echo "🧹 Resetting CSV folders..."
	@docker run --rm -v "$(PWD)/csv_input:/csv" alpine sh -c \
		"rm -rf /csv/processed/* /csv/error/* 2>/dev/null; echo 'Done'"

# ============================================================================
# DBT COMMANDS
# ============================================================================

# Environment variables cho DBT
DBT_ENV := -e POSTGRES_HOST=postgres \
		   -e POSTGRES_PORT=5432 \
		   -e POSTGRES_USER=retail_user \
		   -e POSTGRES_PASSWORD=retail_password \
		   -e POSTGRES_DB=retail_db

# Chạy tất cả models
dbt:
	@echo "🔧 Running DBT models..."
	docker-compose run --rm $(DBT_ENV) dbt deps
	docker-compose run --rm $(DBT_ENV) dbt seed
	docker-compose run --rm $(DBT_ENV) dbt run

# Load seed data
dbt-seed:
	@echo "🌱 Loading DBT seeds..."
	docker-compose run --rm $(DBT_ENV) dbt seed

# Chạy tests
dbt-test:
	@echo "🧪 Running DBT tests..."
	docker-compose run --rm $(DBT_ENV) dbt test

# Generate và serve docs
dbt-docs:
	@echo "📚 Generating DBT docs..."
	docker-compose run --rm $(DBT_ENV) dbt docs generate
	@echo "📖 Starting docs server at http://localhost:8080"
	docker-compose run --rm $(DBT_ENV) -p 8080:8080 dbt docs serve --host 0.0.0.0 --port 8080

# Full DBT workflow
dbt-full: dbt-seed dbt dbt-test
	@echo "✅ DBT full workflow completed!"

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
	@docker-compose exec -T postgres psql -U retail_user -d retail_db -c \
		"TRUNCATE TABLE transaction_details, transactions, products, branches, ml_forecasts RESTART IDENTITY CASCADE;" 2>/dev/null || true
	@docker-compose exec -T clickhouse clickhouse-client -q "TRUNCATE TABLE retail_dw.fact_transactions" 2>/dev/null || true
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
