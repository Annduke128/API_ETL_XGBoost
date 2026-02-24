#!/bin/bash

# ============================================
# Retail Data Pipeline - Deployment Script
# ============================================
# Usage: ./deploy.sh [command] [environment]
# Commands:
#   up          - Start services
#   down        - Stop services
#   build       - Build images

#   status      - Check service status
#   logs        - View logs

# Environments:
#   dev         - Development (default)
#   prod        - Production
# ============================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    cat << EOF
Usage: $0 [command] [options]

Commands:
    up [services]       Start services (default: infrastructure only)
    down [-v]           Stop services (-v to remove volumes)
    build [service]     Build images

    status              Show service status
    logs [service]      View logs

    help                Show this help

Examples:
    $0 up                           # Start infrastructure services
    $0 up ml                        # Start with ML pipeline
    $0 up all                       # Start all services
    $0 down                         # Stop services
    $0 down -v                      # Stop and remove volumes
    $0 build                        # Build all custom images
    $0 logs ml-pipeline             # View ML pipeline logs
EOF
}

cmd_up() {
    local profile=$1
    
    if [ ! -f "$ENV_FILE" ]; then
        log_warn ".env file not found, copying from .env.example"
        cp .env.example .env
    fi

    case "$profile" in
        "ml")
            log_info "Starting infrastructure + ML Pipeline..."
            docker-compose -f $COMPOSE_FILE --profile ml up -d
            ;;
        "sync")
            log_info "Starting infrastructure + Sync Tool..."
            docker-compose -f $COMPOSE_FILE --profile sync up -d
            ;;
        "all")
            log_info "Starting ALL services..."
            docker-compose -f $COMPOSE_FILE --profile ml --profile sync up -d
            ;;
        "init")
            log_info "Running init services..."
            docker-compose -f $COMPOSE_FILE --profile init up -d
            ;;
        "")
            log_info "Starting infrastructure services (redis, postgres, clickhouse, airflow, superset)..."
            docker-compose -f $COMPOSE_FILE up -d redis postgres clickhouse
            sleep 5
            log_info "Starting Airflow..."
            docker-compose -f $COMPOSE_FILE up -d airflow-postgres airflow-init airflow-webserver airflow-scheduler
            log_info "Starting Superset..."
            docker-compose -f $COMPOSE_FILE up -d superset-db superset-cache superset-init superset-web
            log_success "Infrastructure services started!"
            echo ""
            echo "Access points:"
            echo "  - Airflow: http://localhost:8085 (admin/admin)"
            echo "  - Superset: http://localhost:8088 (admin/admin)"
            echo "  - ClickHouse: localhost:8123"
            echo "  - PostgreSQL: localhost:5432"
            ;;
        *)
            log_info "Starting specific service: $profile"
            docker-compose -f $COMPOSE_FILE up -d $profile
            ;;
    esac
}

cmd_down() {
    local remove_volumes=$1
    
    if [ "$remove_volumes" == "-v" ]; then
        log_warn "Stopping services and REMOVING volumes..."
        docker-compose -f $COMPOSE_FILE --profile ml --profile sync --profile init down -v
    else
        log_info "Stopping services..."
        docker-compose -f $COMPOSE_FILE --profile ml --profile sync --profile init down
    fi
    log_success "Services stopped!"
}

cmd_build() {
    local service=$1
    
    if [ -z "$service" ]; then
        log_info "Building all custom images..."
        docker-compose -f $COMPOSE_FILE build --no-cache dbt ml-pipeline sync-tool
    else
        log_info "Building image for: $service"
        docker-compose -f $COMPOSE_FILE build --no-cache $service
    fi
    log_success "Build completed!"
}


cmd_status() {
    echo "============================================"
    echo "Service Status"
    echo "============================================"
    docker-compose -f $COMPOSE_FILE ps
    echo ""
    echo "============================================"
    echo "Resource Usage"
    echo "============================================"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"
}

cmd_logs() {
    local service=$1
    if [ -z "$service" ]; then
        docker-compose -f $COMPOSE_FILE logs -f
    else
        docker-compose -f $COMPOSE_FILE logs -f $service
    fi
}

# Main
main() {
    local command=$1
    shift || true
    
    case "$command" in
        "up")
            cmd_up "$@"
            ;;
        "down")
            cmd_down "$@"
            ;;
        "build")
            cmd_build "$@"
            ;;
        "status")
            cmd_status
            ;;
        "logs")
            cmd_logs "$@"
            ;;

        "help"|"")
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
