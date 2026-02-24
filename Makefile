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
