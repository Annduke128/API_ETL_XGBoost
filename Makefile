# Makefile cho Retail Data Pipeline
# Các lệnh chạy ứng dụng thuần túy (không phụ thuộc Docker)
# 
# Để chạy với Docker, sử dụng: cd docker && make [command]
#

.PHONY: help install test \
        dbt dbt-test dbt-docs dbt-build dbt-build-staging dbt-build-marts dbt-build-full dbt-build-model \
        dbt-deps dbt-seed dbt-list dbt-list-staging dbt-list-marts dbt-list-sources dbt-list-all \
        dbt-preview dbt-show-source dbt-show-model dbt-validate dbt-test-model dbt-compile \
        ml ml-train ml-predict ml-all ml-fast ml-optimal ml-report \
        pipeline-full pipeline-quick app \
        k8s-deploy k8s-deploy-all k8s-update k8s-status k8s-logs k8s-delete \
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
	@echo "║    make ml-fast         - Train without tuning                   ║"
	@echo "║    make ml-optimal      - Train with 100 trials                  ║"
	@echo "║    make ml-all          - Train + Predict + Report               ║"
	@echo "║    make ml-predict      - Generate predictions only              ║"
	@echo "║                                                                  ║"
	@echo "║  CODE QUALITY                                                    ║"
	@echo "║    make format          - Format code (black, isort)             ║"
	@echo "║    make lint            - Lint code (flake8, pylint)             ║"
	@echo "║    make check           - Run all checks                         ║"
	@echo "║                                                                  ║"
	@echo "║  KUBERNETES / K3S                                                ║"
	@echo "║    make app-k3s         - 🚀 Run FULL pipeline on K3s            ║"
	@echo "║    make k3s-spark       - ⚡ Spark ETL (Hybrid)                  ║"
	@echo "║    make k3s-csv         - Process CSV files on K3s               ║"
	@echo "║    make k3s-sync        - Run Sync job on K3s                    ║"
	@echo "║    make k3s-dbt         - Run DBT build on K3s                   ║"
	@echo "║    make k3s-ml-train    - Run ML training on K3s                 ║"
	@echo "║    make k3s-ml-predict  - Run ML predictions on K3s              ║"
	@echo "║    make spark-deploy    - Deploy Spark cluster                   ║"
	@echo "║    make k8s-deploy-all  - Deploy all K3s resources               ║"
	@echo "║    make k8s-status      - Check K3s status                       ║"
	@echo "║                                                                  ║"
	@echo "║  DOCKER                                                          ║"
	@echo "║    cd docker && make help    - Docker commands                   ║"
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
	cd $(DBT_DIR) && dbt $(1) $(DBT_TARGET)
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
	cd $(DBT_DIR) && dbt show --inline "SELECT * FROM {{ source('retail_source', '$(SOURCE)') }} LIMIT $(or $(LIMIT),10)" $(DBT_TARGET)

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
	cd $(DBT_DIR) && dbt docs serve --host 0.0.0.0 --port 8080

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
	cd $(ML_DIR) && $(PYTHON) $(1)
endef

ml: ml-train

ml-train:
	@echo "🤖 Training ML models (Optuna 50 trials)..."
	$(call ml-cmd,train_models.py --trials 50)

ml-fast:
	@echo "⚡ Training ML models (no tuning)..."
	$(call ml-cmd,train_models.py --no-tuning)

ml-optimal:
	@echo "🎯 Training ML models (100 trials)..."
	$(call ml-cmd,train_models.py --trials 100)

ml-all:
	@echo "🚀 Training + Predicting + Report..."
	$(call ml-cmd,xgboost_forecast.py --mode all --trials 30)

ml-predict:
	@echo "📈 Generating predictions..."
	$(call ml-cmd,-c "from xgboost_forecast import SalesForecaster; f = SalesForecaster(); p = f.predict_next_week(); f.save_forecasts(p)")

ml-report:
	@echo "📊 Generating report..."
	$(call ml-cmd,xgboost_forecast.py --mode report)

# ============================================================================
# DATA PROCESSING
# ============================================================================

DATA_DIR := data_cleaning

process:
	@echo "📁 Processing CSV files..."
	cd $(DATA_DIR) && $(PYTHON) auto_process_files.py --input ../csv_input --output ../csv_output

sync-to-ch:
	@echo "🔄 Syncing to ClickHouse..."
	cd $(DATA_DIR) && $(PYTHON) sync_to_clickhouse.py

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
# FULL APPLICATION
# ============================================================================

app: pipeline-full ml-all
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════════╗"
	@echo "║                   ✅ APPLICATION COMPLETE! ✅                         ║"
	@echo "╠══════════════════════════════════════════════════════════════════════╣"
	@echo "║  ✅ All stages completed:                                            ║"
	@echo "║     1. 📁 CSV Processing                                             ║"
	@echo "║     2. 🔄 Sync to ClickHouse                                         ║"
	@echo "║     3. 🏗️  DBT Build                                                 ║"
	@echo "║     4. 🤖 ML Training                                                ║"
	@echo "║     5. 🔮 Predictions                                                ║"
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
	@echo "📜 Recent logs from all pods..."
	$(KUBECTL_CMD) logs --tail=50 -n $(NAMESPACE) -l app=ml-pipeline 2>/dev/null || echo "No ml-pipeline pods found"

k8s-delete: kubectl-check
	@echo "⚠️  WARNING: This will delete all resources in namespace $(NAMESPACE)"
	@read -p "Are you sure? (yes/no): " confirm && [ "$$confirm" = "yes" ] || (echo "Cancelled." && exit 1)
	$(KUBECTL_CMD) delete namespace $(NAMESPACE)
	@echo "✅ Namespace deleted"

# ============================================================================
# RUN PIPELINE ON K3S
# ============================================================================

# Check if kubectl is available
kubectl-check:
	@which k3s kubectl > /dev/null 2>&1 || which kubectl > /dev/null 2>&1 || (echo "❌ kubectl not found. Please install kubectl or k3s." && exit 1)

# Main command: Run full pipeline on K3s
app-k3s: kubectl-check
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════════╗"
	@echo "║           🚀 Running Full Pipeline on K3s Cluster                    ║"
	@echo "╚══════════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "This will execute: Sync → DBT → ML Training → Predictions"
	@echo ""
	@read -p "Continue? (yes/no): " confirm && [ "$$confirm" = "yes" ] || (echo "Cancelled." && exit 1)
	
	@echo ""
	@echo "📁 Step 0: Deleting old jobs (if any)..."
	-$(KUBECTL_CMD) delete job sync-data -n $(NAMESPACE) 2>/dev/null || true
	-$(KUBECTL_CMD) delete job dbt-build -n $(NAMESPACE) 2>/dev/null || true
	-$(KUBECTL_CMD) delete job ml-train -n $(NAMESPACE) 2>/dev/null || true
	-$(KUBECTL_CMD) delete job ml-predict -n $(NAMESPACE) 2>/dev/null || true
	@sleep 2
	
	@echo ""
	@echo "📄 Step 1: Process CSV Files → PostgreSQL"
	@cat $(K8S_DIR)/05-ml-pipeline/job-csv-process.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f - -n $(NAMESPACE)
	@echo "⏳ Waiting for CSV processing to complete..."
	$(KUBECTL_CMD) wait --for=condition=complete job/csv-process -n $(NAMESPACE) --timeout=600s
	@echo "✅ CSV processing complete!"
	
	@echo ""
	@echo "📥 Step 2: Sync PostgreSQL → ClickHouse"
	@cat $(K8S_DIR)/05-ml-pipeline/job-sync.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f - -n $(NAMESPACE)
	@echo "⏳ Waiting for sync to complete..."
	$(KUBECTL_CMD) wait --for=condition=complete job/sync-data -n $(NAMESPACE) --timeout=600s
	@echo "✅ Sync complete!"
	
	@echo ""
	@echo "🏗️ Step 3: DBT Build"
	@cat $(K8S_DIR)/05-ml-pipeline/job-dbt-build.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f - -n $(NAMESPACE)
	@echo "⏳ Waiting for DBT to complete..."
	$(KUBECTL_CMD) wait --for=condition=complete job/dbt-build -n $(NAMESPACE) --timeout=900s
	@echo "✅ DBT build complete!"
	
	@echo ""
	@echo "🤖 Step 4: ML Training"
	@cat $(K8S_DIR)/05-ml-pipeline/job-ml-train.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f - -n $(NAMESPACE)
	@echo "⏳ Waiting for training to complete (this may take 15-30 minutes)..."
	$(KUBECTL_CMD) wait --for=condition=complete job/ml-train -n $(NAMESPACE) --timeout=3600s
	@echo "✅ ML training complete!"
	
	@echo ""
	@echo "🔮 Step 5: Generate Predictions"
	@cat $(K8S_DIR)/05-ml-pipeline/job-ml-predict.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f - -n $(NAMESPACE)
	@echo "⏳ Waiting for predictions..."
	$(KUBECTL_CMD) wait --for=condition=complete job/ml-predict -n $(NAMESPACE) --timeout=600s
	@echo "✅ Predictions complete!"
	
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════════╗"
	@echo "║           ✅ FULL PIPELINE COMPLETE ON K3s!                          ║"
	@echo "╚══════════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Check results: make k3s-logs"

# Individual pipeline steps on K3s
k3s-csv: kubectl-check
	@echo "📄 Running CSV Processing on K3s..."
	-$(KUBECTL_CMD) delete job csv-process -n $(NAMESPACE) 2>/dev/null || true
	@sleep 2
	@cat $(K8S_DIR)/05-ml-pipeline/job-csv-process.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f - -n $(NAMESPACE)
	$(KUBECTL_CMD) wait --for=condition=complete job/csv-process -n $(NAMESPACE) --timeout=600s
	@echo "✅ CSV processing complete!"

k3s-sync: kubectl-check
	@echo "📥 Running Sync on K3s..."
	-$(KUBECTL_CMD) delete job sync-data -n $(NAMESPACE) 2>/dev/null || true
	@sleep 2
	@cat $(K8S_DIR)/05-ml-pipeline/job-sync.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f - -n $(NAMESPACE)
	$(KUBECTL_CMD) wait --for=condition=complete job/sync-data -n $(NAMESPACE) --timeout=600s
	@echo "✅ Sync complete!"

k3s-dbt: kubectl-check
	@echo "🏗️ Running DBT on K3s..."
	-$(KUBECTL_CMD) delete job dbt-build -n $(NAMESPACE) 2>/dev/null || true
	@sleep 2
	@cat $(K8S_DIR)/05-ml-pipeline/job-dbt-build.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f - -n $(NAMESPACE)
	$(KUBECTL_CMD) wait --for=condition=complete job/dbt-build -n $(NAMESPACE) --timeout=900s
	@echo "✅ DBT complete!"

k3s-ml-train: kubectl-check
	@echo "🤖 Running ML Training on K3s..."
	-$(KUBECTL_CMD) delete job ml-train -n $(NAMESPACE) 2>/dev/null || true
	@sleep 2
	@cat $(K8S_DIR)/05-ml-pipeline/job-ml-train.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f - -n $(NAMESPACE)
	$(KUBECTL_CMD) wait --for=condition=complete job/ml-train -n $(NAMESPACE) --timeout=3600s
	@echo "✅ Training complete!"

k3s-ml-predict: kubectl-check
	@echo "🔮 Running ML Predictions on K3s..."
	-$(KUBECTL_CMD) delete job ml-predict -n $(NAMESPACE) 2>/dev/null || true
	@sleep 2
	@cat $(K8S_DIR)/05-ml-pipeline/job-ml-predict.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f - -n $(NAMESPACE)
	$(KUBECTL_CMD) wait --for=condition=complete job/ml-predict -n $(NAMESPACE) --timeout=600s
	@echo "✅ Predictions complete!"

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
	$(KUBECTL_CMD) get pods -n spark
	@echo ""
	@echo "✅ Spark cluster deployed!"
	@echo "   Master UI: kubectl port-forward svc/spark-master 8080:8080 -n spark"

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
	@cat $(K8S_DIR)/05-ml-pipeline/job-spark-etl.yaml | sed 's|$${DOCKERHUB_USERNAME}|$(DOCKERHUB_USERNAME)|g' | $(KUBECTL_CMD) apply -f - -n $(NAMESPACE)
	@echo "⏳ Waiting for Spark ETL to complete (this may take 5-15 minutes)..."
	$(KUBECTL_CMD) wait --for=condition=complete job/spark-etl-hybrid -n $(NAMESPACE) --timeout=1800s
	@echo "✅ Spark ETL complete!"
	
	@echo ""
	@echo "Next steps:"
	@echo "  - Check results: kubectl logs -n $(NAMESPACE) job/spark-etl-hybrid"
	@echo "  - View processed data: kubectl exec -n spark deployment/spark-worker -- ls -la /shared/processed"

spark-status:
	@echo "🔥 Spark Cluster Status"
	@echo "======================="
	@echo "Pods in spark namespace:"
	$(KUBECTL_CMD) get pods -n spark
	@echo ""
	@echo "Services:"
	$(KUBECTL_CMD) get svc -n spark

spark-logs:
	@echo "📜 Spark Master Logs:"
	$(KUBECTL_CMD) logs -n spark deployment/spark-master --tail=50
	@echo ""
	@echo "📜 Spark Worker Logs:"
	$(KUBECTL_CMD) logs -n spark deployment/spark-worker --tail=50

spark-delete:
	@echo "⚠️  Deleting Spark cluster..."
	$(KUBECTL_CMD) delete namespace spark --ignore-not-found=true
	@echo "✅ Spark cluster deleted"

