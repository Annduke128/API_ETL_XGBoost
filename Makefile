# Makefile cho Retail Data Pipeline
# Các lệnh chạy ứng dụng sử dụng Docker (khuyến nghị)
# 
# Các lệnh ML và Data Processing đã được chuyển sang Docker
# để đảm bảo môi trường nhất quán và không cần cài đặt Python dependencies locally
#

.PHONY: help install test check-env \
        dbt dbt-test dbt-docs dbt-build dbt-build-staging dbt-build-marts dbt-build-full dbt-build-model \
        dbt-deps dbt-seed dbt-list dbt-list-staging dbt-list-marts dbt-list-sources dbt-list-all \
        dbt-preview dbt-show-source dbt-show-model dbt-validate dbt-test-model dbt-compile \
        ml ml-train ml-predict ml-all ml-fast ml-optimal ml-report \
        pipeline-full pipeline-quick app app-legacy app-k3s \
        smart-pipeline smart-pipeline-with-sync smart-process smart-dry-run \
        use-k3s use-docker \
        k8s-deploy k8s-deploy-all k8s-update k8s-status k8s-logs k8s-delete \
        k3s-ml-train-gpu k3s-gpu-status k3s-ml-gpu-logs k3s-gpu-test install-gpu-plugin build-push-gpu \
        format lint check

PYTHON := python3
PIP := pip3

# ============================================================================
# HELP & SETUP
# ============================================================================
help:
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║       Retail Data Pipeline - Application Commands                ║"
	@echo "╠══════════════════════════════════════════════════════════════════╣"
	@echo "║  SETUP                                                           ║"
	@echo "║    make install         - Install Python dependencies            ║"
	@echo "║    make test            - Run tests                              ║"
	@echo "║                                                                  ║"
	@echo "║  DBT PIPELINE                                                    ║"
	@echo "║    make dbt-deps        - Install DBT dependencies               ║"
	@echo "║    make dbt-seed        - Load seeds                             ║"
	@echo "║    make dbt-build       - Build all models                       ║"
	@echo "║    make dbt-build-staging  - Build staging only                  ║"
	@echo "║    make dbt-build-marts    - Build marts only                    ║"
	@echo "║    make dbt-test        - Run all tests                          ║"
	@echo "║    make dbt-docs        - Generate & serve docs                  ║"
	@echo "║                                                                  ║"
	@echo "║  DBT LIST & PREVIEW                                              ║"
	@echo "║    make dbt-list-sources    - List all sources                   ║"
	@echo "║    make dbt-list-staging    - List staging models                ║"
	@echo "║    make dbt-list-marts      - List marts models                  ║"
	@echo "║    make dbt-preview MODEL=x - Preview model output               ║"
	@echo "║                                                                  ║"
	@echo "║  ML PIPELINE                                                     ║"
	@echo "║    make ml              - Train ML models                        ║"
	@echo "║    make ml-fast         - Train quick (10 trials)                ║"
	@echo "║    make ml-optimal      - Train with 100 trials                  ║"
	@echo "║    make ml-all          - Train + Predict + Report               ║"
	@echo "║    make ml-predict      - Generate predictions only              ║"
	@echo "║    make ml-po           - Generate Purchase Order (top 50)       ║"
	@echo "║    make ml-po-100       - Generate Purchase Order (top 100)      ║"
	@echo "║                                                                  ║"
	@echo "║  CODE QUALITY                                                    ║"
	@echo "║    make format          - Format code (black, isort)             ║"
	@echo "║    make lint            - Lint code (flake8, pylint)             ║"
	@echo "║    make check           - Run all checks                         ║"
	@echo "║                                                                  ║"
	@echo "║  KUBERNETES / K3S                                                ║"
	@echo "║    make app-k3s         - 🎮 Run FULL pipeline on K3s (GPU)      ║"
	@echo "║    make build-push-k3s  - 🐳 Build & push images (DOCKERHUB_)    ║"
	@echo "║    make k3s-spark       - ⚡ Spark Full Pipeline (Interactive)   ║"
	@echo "║    make k3s-spark-etl   - ⚡ Spark ETL Job only                  ║"
	@echo "║    make k3s-csv         - Process CSV files on K3s               ║"
	@echo "║    make k3s-sync        - Run Sync job on K3s                    ║"
	@echo "║    make k3s-dbt         - Run DBT build on K3s                   ║"
	@echo "║    make k3s-ml-train    - Run ML training on K3s (CPU)           ║"
	@echo "║    make k3s-ml-train-gpu- 🤖 Run ML training on K3s (GPU)        ║"
	@echo "║    make k3s-ml-predict  - Run ML predictions on K3s              ║"
	@echo "║    make spark-deploy    - Deploy Spark cluster                   ║"
	@echo "║    make k8s-deploy-all  - Deploy all K3s resources               ║"
	@echo "║    make k8s-status      - Check K3s status                       ║"
	@echo "║    make k8s-logs        - 📜 Xem logs tất cả jobs                ║"
	@echo "║    make k8s-logs-train  - 📜 Xem logs ML training                ║"
	@echo "║    make k8s-logs-predict- 📜 Xem logs ML predict                 ║"
	@echo "║                                                                  ║"
	@echo "║  🚀 ONE-SHOT COMMANDS (Recommended)                               ║"
	@echo "║    make app             - 🧠 Smart full pipeline (Docker/local)  ║"
	@echo "║    make app-legacy      - 📁 Legacy full pipeline (manual CSV)   ║"
	@echo "║    make app-k3s         - 🎮 Full pipeline on K3s (GPU)          ║"
	@echo "║                                                                  ║"
	@echo "║  📊 PIPELINE MONITOR (Log chi tiết)                              ║"
	@echo "║    make monitor         - Hiển thị tất cả stages                 ║"
	@echo "║    make monitor-spark   - Log Spark ETL processing               ║"
	@echo "║    make monitor-sync    - Log PostgreSQL → ClickHouse sync       ║"
	@echo "║    make monitor-dbt     - Log DBT models build                   ║"
	@echo "║    make monitor-ml      - Log ML Training metrics & KPIs         ║"
	@echo "║    make monitor-forecast- Log Forecast results                   ║"
	@echo "║                                                                  ║"
	@echo "║  SMART PIPELINE (Auto-detect by filename)                        ║"
	@echo "║    make smart-pipeline  - Smart process → Sync → DBT → ML        ║"
	@echo "║    make smart-process   - Auto-detect & process all files        ║"
	@echo "║    make smart-dry-run   - Preview what will be processed         ║"
	@echo "║                                                                  ║"
	@echo "║  LOCAL DOCKER (No Python install needed)                         ║"
	@echo "║    make pipeline-full   - Process CSV → Sync → DBT               ║"
	@echo "║    make process         - Process CSV files                      ║"
	@echo "║    make sync-to-ch      - Sync PostgreSQL → ClickHouse           ║"
	@echo "║    make import-inventory- Import inventory from Excel            ║"
	@echo "║    make ml-all          - Train + Predict + Report (Docker)      ║"
	@echo "║                                                                  ║"
	@echo "║  ENVIRONMENT SWITCHING                                           ║"
	@echo "║    make use-k3s           - Switch from Docker to K3s            ║"
	@echo "║    make use-docker        - Switch from K3s to Docker            ║"
	@echo "║    make check-env         - Check for conflicting environments   ║"
	@echo "║                                                                  ║"
	@echo "║  DOCKER COMPOSE DIRECTORY                                        ║"
	@echo "║    cd docker && make help    - All Docker commands               ║"
	@echo "╚══════════════════════════════════════════════════════════════════╝"

install:
	@echo "📦 Installing dependencies..."
	$(PIP) install -r requirements.txt
	$(PIP) install -r data_cleaning/requirements.txt
	$(PIP) install -r ml_pipeline/requirements.txt
	@echo "✅ Installation complete!"

test:
	@echo "🧪 Running tests..."
	$(PYTHON) -m pytest tests/ -v

# ============================================================================
# CODE QUALITY
# ============================================================================
format:
	@echo "🎨 Formatting code..."
	@which black > /dev/null 2>&1 && black . || echo "⚠️  black not installed"
	@which isort > /dev/null 2>&1 && isort . || echo "⚠️  isort not installed"

lint:
	@echo "🔍 Linting code..."
	@which flake8 > /dev/null 2>&1 && flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics || echo "⚠️  flake8 not installed"
	@which pylint > /dev/null 2>&1 && pylint **/*.py || echo "⚠️  pylint not installed"

check: format lint
	@echo "✅ All checks completed!"

# ============================================================================
# DBT COMMANDS
# ============================================================================

DBT_DIR := dbt_retail
DBT_TARGET := --target clickhouse
DBT_QUIET := --quiet

# Change to dbt directory and run commands
define dbt-cmd
	cd docker && docker-compose run --rm dbt dbt $(1) $(DBT_TARGET)
endef

dbt-deps:
	@echo "📦 Installing DBT dependencies..."
	$(call dbt-cmd,deps)

dbt-seed: dbt-deps
	@echo "🌱 Loading seeds..."
	$(call dbt-cmd,seed)

dbt-list-sources:
	@echo "📋 Listing sources..."
	$(call dbt-cmd,list --select source:*)

dbt-list-staging:
	@echo "📋 Listing staging models..."
	$(call dbt-cmd,list --select staging)

dbt-list-marts:
	@echo "📋 Listing marts models..."
	$(call dbt-cmd,list --select marts)

dbt-list-all:
	@echo "📋 Listing all models..."
	$(call dbt-cmd,list --select staging,marts)

dbt-preview:
	@if [ -z "$(MODEL)" ]; then \
		echo "Usage: make dbt-preview MODEL=stg_products [LIMIT=10]"; \
		exit 1; \
	fi
	@echo "👁️  Previewing $(MODEL)..."
	cd $(DBT_DIR) && dbt show --select $(MODEL) --limit $(or $(LIMIT),10) $(DBT_TARGET)

dbt-show-source:
	@if [ -z "$(SOURCE)" ]; then \
		echo "Usage: make dbt-show-source SOURCE=staging_products [LIMIT=10]"; \
		exit 1; \
	fi
	@echo "👁️  Previewing source $(SOURCE)..."
	cd docker && docker-compose run --rm dbt dbt show --inline "SELECT * FROM {{ source('retail_source', '$(SOURCE)') }} LIMIT $(or $(LIMIT),10)" $(DBT_TARGET)

dbt-build-staging: dbt-seed
	@echo "🔧 Building staging models..."
	$(call dbt-cmd,build --select staging)

dbt-build-marts: dbt-seed
	@echo "🔧 Building marts models..."
	$(call dbt-cmd,build --select marts)

dbt-build: dbt-seed
	@echo "🔧 Building all models..."
	$(call dbt-cmd,build --select staging,marts)

dbt-build-full: dbt-seed
	@echo "🔄 Full refresh build..."
	$(call dbt-cmd,build --select staging,marts --full-refresh)

dbt-build-model:
	@if [ -z "$(MODEL)" ]; then \
		echo "Usage: make dbt-build-model MODEL=dim_product"; \
		exit 1; \
	fi
	@echo "🔧 Building $(MODEL)..."
	$(call dbt-cmd,build --select +$(MODEL))

dbt-test:
	@echo "🧪 Running tests..."
	$(call dbt-cmd,test --select staging,marts)

dbt-compile:
	@echo "🔍 Compiling models..."
	$(call dbt-cmd,compile --select staging,marts)

dbt-docs:
	@echo "📚 Generating docs..."
	$(call dbt-cmd,docs generate)
	@echo "📖 Starting docs server at http://localhost:8080"
	cd docker && docker-compose run --rm -p 8080:8080 dbt dbt docs serve --host 0.0.0.0 --port 8080

dbt-docs-generate:
	@echo "📚 Generating docs..."
	$(call dbt-cmd,docs generate)

# Legacy aliases
dbt: dbt-build
dbt-test-full: dbt-test

# ============================================================================
# ML PIPELINE
# ============================================================================

ML_DIR := ml_pipeline

define ml-cmd
	cd docker && docker-compose --profile ml run --rm ml-pipeline python $(1)
endef

ml: ml-train

ml-train:
	@echo "🤖 Training ML models (Optuna 50 trials)..."
	$(call ml-cmd,train_models.py --trials 50)

ml-fast:
	@echo "⚡ Training ML models (quick - 10 trials)..."
	$(call ml-cmd,train_models.py --trials 10)

ml-optimal:
	@echo "🎯 Training ML models (100 trials)..."
	$(call ml-cmd,train_models.py --trials 100)

ml-all:
	@echo "🚀 Training + Predicting + Report..."
	$(call ml-cmd,xgboost_forecast.py --mode all --trials 30)

ml-predict:
	@echo "📈 Generating predictions..."
	cd docker && docker-compose --profile ml run --rm ml-pipeline python -c "from xgboost_forecast import SalesForecaster; f = SalesForecaster(); p = f.predict_next_week(); f.save_forecasts(p)"

ml-report:
	@echo "📊 Generating report..."
	$(call ml-cmd,xgboost_forecast.py --mode report)

ml-po:
	@echo "📦 Generating Purchase Order (top 50)..."
	$(call ml-cmd,xgboost_forecast.py --mode po --top-n 50)

ml-po-100:
	@echo "📦 Generating Purchase Order (top 100)..."
	$(call ml-cmd,xgboost_forecast.py --mode po --top-n 100)

# ============================================================================
# DATA PROCESSING
# ============================================================================

DATA_DIR := data_cleaning

# ============================================================================
# DOCKER-BASED COMMANDS (Local Development)
# ============================================================================

# Process CSV files using Docker
process:
	@echo "📁 Processing CSV files..."
	cd docker && docker-compose --profile sync run --rm sync-tool python auto_process_files.py --input /csv_input --output /csv_output

# Sync to ClickHouse using Docker
sync-to-ch:
	@echo "🔄 Syncing to ClickHouse..."
	cd docker && docker-compose --profile sync run --rm sync-tool python sync_to_clickhouse.py

# Import inventory using Docker
import-inventory:
	@echo "📦 Importing inventory..."
	cd docker && docker-compose --profile inventory run --rm inventory-import

# Full pipeline using Docker
pipeline-full: sync-to-ch dbt-build
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║     ✅ PIPELINE COMPLETED                                    ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"

pipeline-quick: dbt-build
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║     ✅ QUICK PIPELINE COMPLETED                              ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"

# ============================================================================
# SMART PIPELINE (Auto-detect files by naming convention)
# ============================================================================

# Smart process: Auto-detect file types and process in correct order
smart-process:
	@echo "🧠 Smart Processing: Auto-detecting files by naming convention..."
	cd docker && docker-compose --profile smart run --rm smart-processor python smart_processor.py --input /csv_input --output /csv_output

# Smart dry-run: Preview what files will be processed without actually processing
smart-dry-run:
	@echo "🔍 Smart Dry-Run: Preview processing plan..."
	cd docker && docker-compose --profile smart run --rm smart-processor python smart_processor.py --input /csv_input --output /csv_output --dry-run

# Check environment to prevent conflicts
check-env:
	@docker ps --format "table {% raw %}{{.Names}}{% endraw %}" 2>/dev/null | grep -q "retail_" && \
		(echo "⚠️  WARNING: Docker containers are running!"; \
		 echo "   Run 'make use-k3s' to switch to K3s, or"; \
		 echo "   Run 'make down' to stop Docker first.") || true
	@kubectl get pods -n hasu-ml --no-headers 2>/dev/null | grep -q Running && \
		(echo "⚠️  WARNING: K3s pods are running in hasu-ml namespace!"; \
		 echo "   Run 'make use-docker' to switch to Docker, or"; \
		 echo "   Run 'kubectl delete namespace hasu-ml spark' to clean K3s.") || true

# Smart pipeline with sync: Process files → Sync → DBT
smart-pipeline-with-sync: check-env smart-process sync-to-ch dbt-build
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║     ✅ SMART PIPELINE (with sync) COMPLETED                  ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"

# Full smart pipeline: Process → Sync → DBT → ML
smart-pipeline: smart-process sync-to-ch dbt-build ml-all
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════════╗"
	@echo "║     ✅ FULL SMART PIPELINE COMPLETED!                                 ║"
	@echo "║                                                                       ║"
	@echo "║     Steps completed:                                                  ║"
	@echo "║     1. 🧠 Smart file detection & processing                          ║"
	@echo "║     2. 🔄 Sync to ClickHouse                                           ║"
	@echo "║     3. 🏗️  DBT Build                                                   ║"
	@echo "║     4. 🤖 ML Training & Prediction                                     ║"
	@echo "╚══════════════════════════════════════════════════════════════════════╝"

# ============================================================================
# FULL APPLICATION (Local Development with Docker)
# ============================================================================

# ============================================================================
# ENVIRONMENT SWITCHING (Docker ↔ K3s)
# ============================================================================

# Switch from Docker to K3s (stop Docker first)
use-k3s:
	@echo "🔄 Switching from Docker to K3s..."
	@echo "📋 Stopping Docker Compose..."
	cd docker && docker-compose down
	@echo "✅ Docker stopped. You can now use K3s commands:"
	@echo "   make k8s-deploy-all    - Deploy to K3s"
	@echo "   make app-k3s           - Run pipeline on K3s"

# Switch from K3s to Docker (clean K3s resources)
use-docker:
	@echo "🔄 Switching from K3s to Docker..."
	@echo "⚠️  Cleaning K3s namespaces..."
	-$(KUBECTL_CMD) delete namespace hasu-ml 2>/dev/null || true
	-$(KUBECTL_CMD) delete namespace spark 2>/dev/null || true
	@echo "⏳ Waiting for cleanup..."
	@sleep 5
	@echo "📋 Starting Docker Compose..."
	cd docker && make up
	@echo "✅ Docker started. You can now use:"
	@echo "   make app    - Run pipeline locally"

# ============================================================================
# PIPELINE MONITOR - Log chi tiết cho từng stage
# ============================================================================

# ============================================================================
# PIPELINE MONITOR - Log chi tiết cho từng stage (chạy trong Docker)
# ============================================================================

# Monitor tất cả các stages
monitor:
	@echo "📊 Running Pipeline Monitor..."
	@cd docker && docker-compose --profile ml run --rm ml-pipeline python /app/pipeline_monitor.py all 2>/dev/null || \
		echo "⚠️  Monitor cần containers đang chạy. Hãy chạy 'make app' trước."

# Monitor từng stage
monitor-spark:
	@cd docker && docker-compose --profile ml run --rm ml-pipeline python /app/pipeline_monitor.py spark 2>/dev/null || \
		echo "⚠️  Monitor cần containers đang chạy."

monitor-sync:
	@cd docker && docker-compose --profile ml run --rm ml-pipeline python /app/pipeline_monitor.py sync 2>/dev/null || \
		echo "⚠️  Monitor cần containers đang chạy."

monitor-dbt:
	@cd docker && docker-compose --profile ml run --rm ml-pipeline python /app/pipeline_monitor.py dbt 2>/dev/null || \
		echo "⚠️  Monitor cần containers đang chạy."

monitor-ml:
	@cd docker && docker-compose --profile ml run --rm ml-pipeline python /app/pipeline_monitor.py ml 2>/dev/null || \
		echo "⚠️  Monitor cần containers đang chạy."

monitor-forecast:
	@cd docker && docker-compose --profile ml run --rm ml-pipeline python /app/pipeline_monitor.py forecast 2>/dev/null || \
		echo "⚠️  Monitor cần containers đang chạy."

# ============================================================================
# ONE-SHOT FULL APPLICATION COMMANDS
# ============================================================================

# 🚀 DEFAULT: Smart Pipeline (Recommended - Auto-detect files by naming convention)
app: check-env smart-pipeline monitor
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════════╗"
	@echo "║              ✅ SMART APPLICATION COMPLETE! ✅                        ║"
	@echo "╠══════════════════════════════════════════════════════════════════════╣"
	@echo "║  ✅ All stages completed with Smart Processing:                      ║"
	@echo "║     1. 🧠 Smart Detection & Processing (Products→Inventory→Sales)    ║"
	@echo "║     2. 🔄 Sync to ClickHouse                                         ║"
	@echo "║     3. 🏗️  DBT Build                                                 ║"
	@echo "║     4. 🤖 ML Training                                                ║"
	@echo "║     5. 🔮 Predictions                                                ║"
	@echo "║                                                                      ║"
	@echo "║  📊 Xem chi tiết ở trên (Pipeline Monitor logs)                      ║"
	@echo "╚══════════════════════════════════════════════════════════════════════╝"

# 🔄 Legacy: Original pipeline (manual CSV processing, no smart detection)
app-legacy: pipeline-full ml-all monitor
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════════╗"
	@echo "║              ✅ LEGACY APPLICATION COMPLETE! ✅                       ║"
	@echo "╠══════════════════════════════════════════════════════════════════════╣"
	@echo "║  ✅ All stages completed:                                            ║"
	@echo "║     1. 📁 CSV Processing (Legacy)                                    ║"
	@echo "║     2. 🔄 Sync to ClickHouse                                         ║"
	@echo "║     3. 🏗️  DBT Build                                                 ║"
	@echo "║     4. 🤖 ML Training                                                ║"
	@echo "║     5. 🔮 Predictions                                                ║"
	@echo "║                                                                      ║"
	@echo "║  📊 Xem chi tiết ở trên (Pipeline Monitor logs)                      ║"
	@echo "╚══════════════════════════════════════════════════════════════════════╝"

# ============================================================================
# KUBERNETES / K3S COMMANDS
# ============================================================================

K8S_DIR := k8s
NAMESPACE := hasu-ml
KUBECTL := kubectl
DOCKERHUB_USERNAME ?= your-dockerhub-user  # Override with: make app-k3s DOCKERHUB_USERNAME=myuser

# Check if running on K3s
ifeq ($(shell which k3s 2>/dev/null),)
    KUBECTL_CMD := $(KUBECTL)
else
    KUBECTL_CMD := k3s kubectl
endif

# Check if kubectl is available
kubectl-check:
	@which $(KUBECTL) > /dev/null 2>&1 || (echo "❌ kubectl not found. Please install kubectl or k3s." && exit 1)

k8s-deploy: kubectl-check
	@echo "🚀 Deploying/updating application on K3s..."
	@echo "📦 Updating images and restarting deployments..."
	$(KUBECTL_CMD) set image cronjob/ml-training ml-training=$${DOCKERHUB_USERNAME:-localhost}/hasu-ml-pipeline:latest -n $(NAMESPACE) 2>/dev/null || true
	$(KUBECTL_CMD) set image cronjob/ml-predict ml-predict=$${DOCKERHUB_USERNAME:-localhost}/hasu-ml-pipeline:latest -n $(NAMESPACE) 2>/dev/null || true
	$(KUBECTL_CMD) set image cronjob/dbt-daily dbt=$${DOCKERHUB_USERNAME:-localhost}/hasu-dbt:latest -n $(NAMESPACE) 2>/dev/null || true
	$(KUBECTL_CMD) rollout restart deployment/airflow-webserver -n $(NAMESPACE) 2>/dev/null || true
	$(KUBECTL_CMD) rollout restart deployment/airflow-scheduler -n $(NAMESPACE) 2>/dev/null || true
	$(KUBECTL_CMD) rollout restart deployment/superset -n $(NAMESPACE) 2>/dev/null || true
	@echo "✅ Deployment update triggered!"
	@echo "⏳ Check status with: make k8s-status"

k8s-deploy-all: kubectl-check
	@echo "🚀 Full deployment to K3s..."
	@echo "📁 Creating namespace..."
	$(KUBECTL_CMD) create namespace $(NAMESPACE) 2>/dev/null || echo "Namespace already exists"
	@echo "📦 Applying namespace, storage, config, databases, applications..."
	$(KUBECTL_CMD) apply -f $(K8S_DIR)/00-namespace/
	$(KUBECTL_CMD) apply -f $(K8S_DIR)/01-storage/
	$(KUBECTL_CMD) apply -f $(K8S_DIR)/02-config/
	$(KUBECTL_CMD) apply -f $(K8S_DIR)/03-databases/
	$(KUBECTL_CMD) apply -f $(K8S_DIR)/04-applications/
	@echo "📦 Applying ML pipeline manifests with image substitution..."
	@for file in $(K8S_DIR)/05-ml-pipeline/*.yaml; do \
		echo "  Applying $$file..."; \
		sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' $$file | $(KUBECTL_CMD) apply -f -; \
	done
	@echo "✅ All resources applied!"
	@echo "⏳ Waiting for pods to start..."
	sleep 10
	$(KUBECTL_CMD) get pods -n $(NAMESPACE)
	@echo ""
	@echo "📋 Next steps:"
	@echo "  1. Copy CSV files to PVC: kubectl cp csv_input/. $(NAMESPACE)/<pod>:/csv_input/"
	@echo "  2. Run pipeline: make app-k3s DOCKERHUB_USERNAME=$(DOCKERHUB_USERNAME)"

k8s-update: k8s-deploy

k8s-status: kubectl-check
	@echo "📊 K3s Deployment Status"
	@echo "========================"
	@echo ""
	@echo "📦 Deployments:"
	$(KUBECTL_CMD) get deployments -n $(NAMESPACE)
	@echo ""
	@echo "🔄 CronJobs:"
	$(KUBECTL_CMD) get cronjobs -n $(NAMESPACE)
	@echo ""
	@echo "🟢 Pods:"
	$(KUBECTL_CMD) get pods -n $(NAMESPACE)

k8s-logs: kubectl-check
	@echo "📜 Viewing logs from all jobs..."
	./k8s/scripts/view_all_logs.sh -n $(NAMESPACE)

k8s-logs-follow: kubectl-check
	@echo "📜 Following logs from latest job..."
	./k8s/scripts/view_all_logs.sh -n $(NAMESPACE) --last -f

k8s-logs-train: kubectl-check
	@echo "📜 Viewing ML training logs..."
	./k8s/scripts/view_all_logs.sh -n $(NAMESPACE) -j ml-train

k8s-logs-predict: kubectl-check
	@echo "📜 Viewing ML predict logs..."
	./k8s/scripts/view_all_logs.sh -n $(NAMESPACE) -j ml-predict

k8s-logs-etl: kubectl-check
	@echo "📜 Viewing ETL logs..."
	./k8s/scripts/view_all_logs.sh -n $(NAMESPACE) -j spark-etl

k8s-logs-dbt: kubectl-check
	@echo "📜 Viewing DBT logs..."
	./k8s/scripts/view_all_logs.sh -n $(NAMESPACE) -j dbt-build

k8s-delete: kubectl-check
	@echo "⚠️  WARNING: This will delete all resources in namespace $(NAMESPACE)"
	@read -p "Are you sure? (yes/no): " confirm && [ "$$confirm" = "yes" ] || (echo "Cancelled." && exit 1)
	$(KUBECTL_CMD) delete namespace $(NAMESPACE)
	@echo "✅ Namespace deleted"

# ============================================================================
# RUN PIPELINE ON K3S
# ============================================================================

# Main command: Run full pipeline on K3s (Using Spark Hybrid ETL)
app-k3s: kubectl-check
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════════╗"
	@echo "║           🚀 Running Full Pipeline on K3s Cluster                    ║"
	@echo "║           Using Spark Hybrid Architecture + GPU                      ║"
	@echo "╚══════════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Pipeline: Spark ETL → Python UDFs → DBT → ML Training (GPU) → Predictions"
	@echo ""
	@read -p "Continue? (yes/no): " confirm && [ "$$confirm" = "yes" ] || (echo "Cancelled." && exit 1)
	
	@echo ""
	@echo "📋 Checking GPU node..."
	$(KUBECTL_CMD) get nodes -l nvidia.com/gpu.present=true --show-labels 2>/dev/null | grep -q "k3s-worker-gpu" || (echo "❌ GPU node not found! Run: make install-gpu-plugin" && exit 1)
	@echo "✅ GPU node found: k3s-worker-gpu"
	
	@echo ""
	@echo "📁 Step 0: Ensure Spark cluster is ready..."
	$(KUBECTL_CMD) get pods -n $(NAMESPACE) -l app=spark-master 2>/dev/null | grep -q Running || (echo "⚠️  Spark not deployed. Deploying Spark..." && $(KUBECTL_CMD) apply -f $(K8S_DIR)/spark/)
	@sleep 5
	
	@echo ""
	@echo "⚡ Step 1: Spark Hybrid ETL (CSV → PostgreSQL → ClickHouse)"
	-$(KUBECTL_CMD) delete job spark-etl -n $(NAMESPACE) 2>/dev/null || true
	@sleep 2
	@cat $(K8S_DIR)/05-ml-pipeline/job-spark-etl.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f -
	@echo "⏳ Waiting for Spark ETL to complete (5-15 minutes)..."
	$(KUBECTL_CMD) wait --for=condition=complete job/spark-etl -n $(NAMESPACE) --timeout=1800s
	@echo "✅ Spark ETL complete!"
	
	@echo ""
	@echo "🔄 Step 2: Sync PostgreSQL → ClickHouse"
	-$(KUBECTL_CMD) delete job sync-data -n $(NAMESPACE) 2>/dev/null || true
	@sleep 2
	@cat $(K8S_DIR)/05-ml-pipeline/job-sync.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f -
	@echo "⏳ Waiting for sync to complete..."
	$(KUBECTL_CMD) wait --for=condition=complete job/sync-data -n $(NAMESPACE) --timeout=600s
	@echo "✅ Sync complete!"
	
	@echo ""
	@echo "🏗️ Step 3: DBT Build"
	-$(KUBECTL_CMD) delete job dbt-build -n $(NAMESPACE) 2>/dev/null || true
	@sleep 2
	@cat $(K8S_DIR)/05-ml-pipeline/job-dbt-build.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f -
	@echo "⏳ Waiting for DBT to complete..."
	$(KUBECTL_CMD) wait --for=condition=complete job/dbt-build -n $(NAMESPACE) --timeout=900s
	@echo "✅ DBT build complete!"
	
	@echo ""
	@echo "🤖 Step 4: ML Training with GPU"
	-$(KUBECTL_CMD) delete job ml-train-gpu -n $(NAMESPACE) 2>/dev/null || true
	@sleep 2
	@cat $(K8S_DIR)/05-ml-pipeline/job-ml-train-gpu.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f -
	@echo "⏳ Waiting for GPU training to complete (faster with GPU)..."
	$(KUBECTL_CMD) wait --for=condition=complete job/ml-train-gpu -n $(NAMESPACE) --timeout=1800s
	@echo "✅ GPU ML training complete!"
	
	@echo ""
	@echo "🔮 Step 5: Generate Predictions"
	-$(KUBECTL_CMD) delete job ml-predict -n $(NAMESPACE) 2>/dev/null || true
	@sleep 2
	@cat $(K8S_DIR)/05-ml-pipeline/job-ml-predict.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f -
	@echo "⏳ Waiting for predictions..."
	$(KUBECTL_CMD) wait --for=condition=complete job/ml-predict -n $(NAMESPACE) --timeout=600s
	@echo "✅ Predictions complete!"
	
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════════╗"
	@echo "║           ✅ FULL PIPELINE WITH GPU COMPLETE ON K3s!                 ║"
	@echo "╚══════════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Check results: make k3s-logs"

# Full pipeline on K3s with GPU for ML Training
	@echo "📄 Running CSV Processing on K3s..."
	-$(KUBECTL_CMD) delete job csv-process -n $(NAMESPACE) 2>/dev/null || true
	@sleep 2
	@cat $(K8S_DIR)/05-ml-pipeline/job-csv-process.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f -
	$(KUBECTL_CMD) wait --for=condition=complete job/csv-process -n $(NAMESPACE) --timeout=600s
	@echo "✅ CSV processing complete!"

k3s-sync: kubectl-check
	@echo "📥 Running Sync on K3s..."
	-$(KUBECTL_CMD) delete job sync-data -n $(NAMESPACE) 2>/dev/null || true
	@sleep 2
	@cat $(K8S_DIR)/05-ml-pipeline/job-sync.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f -
	$(KUBECTL_CMD) wait --for=condition=complete job/sync-data -n $(NAMESPACE) --timeout=600s
	@echo "✅ Sync complete!"

k3s-dbt: kubectl-check
	@echo "🏗️ Running DBT on K3s..."
	-$(KUBECTL_CMD) delete job dbt-build -n $(NAMESPACE) 2>/dev/null || true
	@sleep 2
	@cat $(K8S_DIR)/05-ml-pipeline/job-dbt-build.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f -
	$(KUBECTL_CMD) wait --for=condition=complete job/dbt-build -n $(NAMESPACE) --timeout=900s
	@echo "✅ DBT complete!"

k3s-ml-train: kubectl-check
	@echo "🤖 Running ML Training on K3s..."
	-$(KUBECTL_CMD) delete job ml-train -n $(NAMESPACE) 2>/dev/null || true
	@sleep 2
	@cat $(K8S_DIR)/05-ml-pipeline/job-ml-train.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f -
	$(KUBECTL_CMD) wait --for=condition=complete job/ml-train -n $(NAMESPACE) --timeout=3600s
	@echo "✅ Training complete!"

k3s-ml-predict: kubectl-check
	@echo "🔮 Running ML Predictions on K3s..."
	-$(KUBECTL_CMD) delete job ml-predict -n $(NAMESPACE) 2>/dev/null || true
	@sleep 2
	@cat $(K8S_DIR)/05-ml-pipeline/job-ml-predict.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f -
	$(KUBECTL_CMD) wait --for=condition=complete job/ml-predict -n $(NAMESPACE) --timeout=600s
	@echo "✅ Predictions complete!"

k3s-spark-etl: kubectl-check
	@echo "⚡ Running Spark ETL on K3s..."
	-$(KUBECTL_CMD) delete job spark-etl -n $(NAMESPACE) 2>/dev/null || true
	@sleep 2
	@cat $(K8S_DIR)/05-ml-pipeline/job-spark-etl.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f -
	@echo "⏳ Waiting for Spark ETL to complete (5-15 minutes)..."
	$(KUBECTL_CMD) wait --for=condition=complete job/spark-etl -n $(NAMESPACE) --timeout=1800s
	@echo "✅ Spark ETL complete!"

# Copy CSV files to K3s PVC
k3s-copy-csv: kubectl-check
	@echo "📁 Copying CSV files to K3s..."
	@echo "Creating temporary pod to access PVC..."
	@$(KUBECTL_CMD) run csv-uploader -n $(NAMESPACE) --image=busybox:1.36 --restart=Never -- sleep 300 2>/dev/null || true
	@sleep 3
	@echo "Copying files from csv_input/ to K3s..."
	@$(KUBECTL_CMD) cp csv_input/. $(NAMESPACE)/csv-uploader:/tmp/csv_input/ 2>/dev/null || echo "⚠️  Copy may have failed, continuing..."
	@$(KUBECTL_CMD) exec -n $(NAMESPACE) csv-uploader -- sh -c 'mkdir -p /csv_input && cp -r /tmp/csv_input/* /csv_input/ 2>/dev/null; ls -la /csv_input/' || true
	@$(KUBECTL_CMD) delete pod csv-uploader -n $(NAMESPACE) --force 2>/dev/null || true
	@echo "✅ CSV files copied!"
	@echo ""
	@echo "To verify, run: kubectl exec -n $(NAMESPACE) deployment/postgres -- ls -la /csv_input"

# Build and push Docker images for K3s
build-push-k3s:
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════════╗"
	@echo "║         🐳 Build & Push Docker Images cho K3s                        ║"
	@echo "╚══════════════════════════════════════════════════════════════════════╝"
	@echo ""
	@if [ -z "$(DOCKERHUB_USERNAME)" ] || [ "$(DOCKERHUB_USERNAME)" = "your-dockerhub-user" ]; then \
		echo "❌ Lỗi: Cần cung cấp DOCKERHUB_USERNAME"; \
		echo "Usage: make build-push-k3s DOCKERHUB_USERNAME=myusername"; \
		exit 1; \
	fi
	@./build-and-push-k3s.sh $(DOCKERHUB_USERNAME)

# Deploy commands
k3s-deploy: kubectl-check
	@echo "🚀 Updating images on K3s..."
	$(KUBECTL_CMD) rollout restart deployment/airflow-webserver -n $(NAMESPACE) || true
	$(KUBECTL_CMD) rollout restart deployment/airflow-scheduler -n $(NAMESPACE) || true
	$(KUBECTL_CMD) rollout restart deployment/superset -n $(NAMESPACE) || true
	@echo "✅ Restart triggered!"

k3s-status: kubectl-check
	@echo "📊 K3s Status"
	@echo "============="
	@echo "Jobs:"
	$(KUBECTL_CMD) get jobs -n $(NAMESPACE)
	@echo ""
	@echo "Pods:"
	$(KUBECTL_CMD) get pods -n $(NAMESPACE)

k3s-logs: kubectl-check
	@echo "📜 Logs from latest jobs..."
	$(KUBECTL_CMD) logs -n $(NAMESPACE) job/sync-data --tail=50 2>/dev/null || echo "No sync logs"
	$(KUBECTL_CMD) logs -n $(NAMESPACE) job/ml-train --tail=50 2>/dev/null || echo "No training logs"

# ============================================================================
# SPARK ETL (Hybrid Architecture)
# ============================================================================

spark-deploy: kubectl-check
	@echo "🚀 Deploying Spark Cluster..."
	$(KUBECTL_CMD) apply -f $(K8S_DIR)/spark/00-namespace.yaml
	$(KUBECTL_CMD) apply -f $(K8S_DIR)/spark/01-storage.yaml
	$(KUBECTL_CMD) apply -f $(K8S_DIR)/spark/02-spark-master.yaml
	$(KUBECTL_CMD) apply -f $(K8S_DIR)/spark/03-spark-worker.yaml
	$(KUBECTL_CMD) apply -f $(K8S_DIR)/spark/04-spark-history-server.yaml
	@echo "⏳ Waiting for Spark to be ready..."
	sleep 10
	@echo "Checking Spark status..."
	$(KUBECTL_CMD) get pods -n $(NAMESPACE) -l app=spark-master,app=spark-worker
	@echo ""
	@echo "✅ Spark cluster deployed!"
	@echo "   Master UI: kubectl port-forward svc/spark-master 8080:8080 -n $(NAMESPACE)"

k3s-spark: kubectl-check
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════════╗"
	@echo "║           ⚡ Spark Hybrid ETL Pipeline                               ║"
	@echo "╚══════════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Pipeline: Spark(Scala) → Python(UDFs) → PostgreSQL → ClickHouse"
	@echo ""
	@read -p "Continue? (yes/no): " confirm && [ "$$confirm" = "yes" ] || (echo "Cancelled." && exit 1)
	
	@echo ""
	@echo "📁 Step 1: Running Spark ETL (Heavy Lifting)..."
	-$(KUBECTL_CMD) delete job spark-etl -n $(NAMESPACE) 2>/dev/null || true
	@sleep 2
	@cat $(K8S_DIR)/05-ml-pipeline/job-spark-etl.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f -
	@echo "⏳ Waiting for Spark ETL to complete (this may take 5-15 minutes)..."
	$(KUBECTL_CMD) wait --for=condition=complete job/spark-etl -n $(NAMESPACE) --timeout=1800s
	@echo "✅ Spark ETL complete!"
	
	@echo ""
	@echo "Next steps:"
	@echo "  - Check results: kubectl logs -n $(NAMESPACE) job/spark-etl"
	@echo "  - View processed data: kubectl exec -n $(NAMESPACE) deployment/spark-worker -- ls -la /shared/processed"

spark-status:
	@echo "🔥 Spark Cluster Status"
	@echo "======================="
	@echo "Pods in spark namespace:"
	$(KUBECTL_CMD) get pods -n $(NAMESPACE) -l app=spark-master,app=spark-worker
	@echo ""
	@echo "Services:"
	$(KUBECTL_CMD) get svc -n $(NAMESPACE) spark-master

spark-logs:
	@echo "📜 Spark Master Logs:"
	$(KUBECTL_CMD) logs -n $(NAMESPACE) deployment/spark-master --tail=50
	@echo ""
	@echo "📜 Spark Worker Logs:"
	$(KUBECTL_CMD) logs -n $(NAMESPACE) deployment/spark-worker --tail=50

spark-delete:
	@echo "⚠️  Deleting Spark cluster..."
	$(KUBECTL_CMD) delete namespace spark --ignore-not-found=true
	@echo "✅ Spark cluster deleted"


# ============================================================================
# GPU ML TRAINING
# ============================================================================
# 
# Các lệnh GPU:
#   make k3s-gpu-test        - Test GPU trong container
#   make k3s-gpu-status      - Kiểm tra GPU status
#   make k3s-ml-train-gpu    - Chạy ML training với GPU
#   make k3s-ml-gpu-logs     - Xem logs GPU training
#   make app-k3s-gpu         - Chạy toàn bộ pipeline với GPU
#

# Run ML training with GPU on K3s
k3s-ml-train-gpu: kubectl-check
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════════╗"
	@echo "║           🤖 Running ML Training with GPU on K3s                     ║"
	@echo "║           Target: k3s-worker-gpu (RTX 3060)                          ║"
	@echo "╚══════════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "📋 Checking GPU node..."
	$(KUBECTL_CMD) get nodes -l nvidia.com/gpu.present=true --show-labels 2>/dev/null | grep -q "k3s-worker-gpu" || (echo "❌ GPU node not found!" && exit 1)
	@echo "✅ GPU node found"
	@echo ""
	-$(KUBECTL_CMD) delete job ml-train-gpu -n $(NAMESPACE) 2>/dev/null || true
	@sleep 2
	@cat $(K8S_DIR)/05-ml-pipeline/job-ml-train-gpu.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f - -n $(NAMESPACE)
	@echo ""
	@echo "⏳ Waiting for GPU training to start..."
	@sleep 5
	@echo "📜 Streaming logs (Ctrl+C to stop watching, job will continue running):"
	@echo ""
	$(KUBECTL_CMD) logs -n $(NAMESPACE) job/ml-train-gpu -f 2>/dev/null || \
		($(KUBECTL_CMD) wait --for=condition=complete job/ml-train-gpu -n $(NAMESPACE) --timeout=3600s && \
		 echo "" && echo "✅ GPU Training complete!")

# Install NVIDIA Device Plugin (run once)
install-gpu-plugin: kubectl-check
	@echo "📦 Installing NVIDIA Device Plugin..."
	@bash $(K8S_DIR)/scripts/install-gpu-operator.sh

# Check GPU status on cluster
k3s-gpu-status: kubectl-check
	@echo "🎮 GPU Status"
	@echo "============="
	@echo ""
	@echo "📊 Nodes with GPU:"
	@$(KUBECTL_CMD) get nodes -o custom-columns=NAME:.metadata.name,GPU:.status.capacity.nvidia\.com/gpu,READY:.status.conditions[-1].type 2>/dev/null || \
		echo "  (Cannot get GPU info)"
	@echo ""
	@echo "📋 GPU Labels on nodes:"
	@$(KUBECTL_CMD) get nodes --show-labels | grep -o 'nvidia.com/gpu[^,]*' | sort -u || echo "  (No GPU labels found)"
	@echo ""
	@echo "🟢 GPU Pods (running):"
	@$(KUBECTL_CMD) get pods --all-namespaces -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,GPU:.spec.containers[*].resources.limits.nvidia\.com/gpu,STATUS:.status.phase 2>/dev/null | grep -v "<none>" || \
		echo "  (No GPU pods found)"

# Build and push GPU image
build-push-gpu: check-env
	@echo "🐳 Building GPU image..."
	@docker build -f ml_pipeline/Dockerfile.gpu -t $(DOCKERHUB_USERNAME)/hasu-ml-pipeline:gpu-latest ml_pipeline/
	@echo "📤 Pushing GPU image to Docker Hub..."
	@docker push $(DOCKERHUB_USERNAME)/hasu-ml-pipeline:gpu-latest
	@echo "✅ GPU image pushed!"

# Check GPU job logs
k3s-ml-gpu-logs: kubectl-check
	@echo "📜 GPU Training Logs:"
	$(KUBECTL_CMD) logs -n $(NAMESPACE) job/ml-train-gpu --tail=100

# Check if GPU is detected inside container
k3s-gpu-test: kubectl-check
	@echo "🎮 Testing GPU inside container..."
	$(KUBECTL_CMD) run gpu-test -n $(NAMESPACE) --image=nvidia/cuda:12.1.0-base-ubuntu22.04 --rm -it --restart=Never -- nvidia-smi || \
	echo "⚠️  Không thể chạy nvidia-smi trong container (có thể cần cấu hình thêm)"
