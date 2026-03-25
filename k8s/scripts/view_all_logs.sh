#!/bin/bash
# ============================================================
# Script: view_all_logs.sh
# Mô tả: Hiển thị tất cả logs từ các jobs trong pipeline
# Usage: ./view_all_logs.sh [options]
#   -f, --follow     : Theo dõi real-time (chỉ job đang chạy)
#   -n, --namespace  : Namespace (mặc định: hasu-ml)
#   -j, --job        : Chỉ xem 1 job cụ thể
#   --last           : Xem job chạy gần nhất
#   -h, --help       : Hiển thị help
# ============================================================

set -e

# Default values
NAMESPACE="hasu-ml"
FOLLOW_MODE=false
SPECIFIC_JOB=""
SHOW_LAST=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Help function
show_help() {
    echo -e "${BOLD}Usage:${NC} $0 [options]"
    echo ""
    echo -e "${BOLD}Options:${NC}"
    echo "  -f, --follow       Theo dõi real-time (chỉ cho job đang chạy)"
    echo "  -n, --namespace    Namespace (mặc định: hasu-ml)"
    echo "  -j, --job JOB      Chỉ xem 1 job cụ thể"
    echo "  --last             Chỉ xem job chạy gần nhất"
    echo "  -h, --help         Hiển thị help này"
    echo ""
    echo -e "${BOLD}Ví dụ:${NC}"
    echo "  $0                           # Xem tất cả logs"
    echo "  $0 -f                        # Theo dõi real-time"
    echo "  $0 -j ml-train               # Chỉ xem job ml-train"
    echo "  $0 -j ml-train -f            # Theo dõi ml-train real-time"
    echo "  $0 --last                    # Xem job gần nhất"
    echo "  $0 -n default                # Xem namespace khác"
    echo ""
    echo -e "${BOLD}Các jobs chính:${NC}"
    echo "  spark-etl        : ETL CSV → PostgreSQL"
    echo "  sync-data        : Sync PostgreSQL → ClickHouse"
    echo "  dbt-build        : DBT models build"
    echo "  dbt-test         : DBT tests"
    echo "  ml-train         : ML training (XGBoost + Optuna)"
    echo "  ml-predict       : ML predictions + email"
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow)
            FOLLOW_MODE=true
            shift
            ;;
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -j|--job)
            SPECIFIC_JOB="$2"
            shift 2
            ;;
        --last)
            SHOW_LAST=true
            shift
            ;;
        -h|--help)
            show_help
            ;;
        *)
            echo -e "${RED}Lỗi:${NC} Không hiểu option: $1"
            echo "Chạy '$0 --help' để xem hướng dẫn"
            exit 1
            ;;
    esac
done

# Function: Print section header
print_header() {
    echo ""
    echo -e "${MAGENTA}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║${NC} ${BOLD}$1${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════════════╝${NC}"
}

# Function: Print subsection
print_subheader() {
    echo ""
    echo -e "${CYAN}▶ $1${NC}"
    echo -e "${CYAN}─────────────────────────────────────────────────────────────────${NC}"
}

# Function: Get job status
get_job_status() {
    local job_name=$1
    kubectl get job -n "$NAMESPACE" "$job_name" -o jsonpath='{.status.conditions[0].type}' 2>/dev/null || echo "Unknown"
}

# Function: Get job completion time
get_job_age() {
    local job_name=$1
    kubectl get job -n "$NAMESPACE" "$job_name" -o jsonpath='{.status.completionTime}' 2>/dev/null | xargs -I {} date -d "{}" +"%Y-%m-%d %H:%M:%S" 2>/dev/null || echo "N/A"
}

# Function: Check if job exists
job_exists() {
    kubectl get job -n "$NAMESPACE" "$1" &>/dev/null
}

# Function: Check if job is running
is_job_running() {
    local job_name=$1
    local active=$(kubectl get job -n "$NAMESPACE" "$job_name" -o jsonpath='{.status.active}' 2>/dev/null || echo "0")
    [[ "$active" == "1" ]]
}

# Function: Show job logs
show_job_logs() {
    local job_name=$1
    local follow=${2:-false}
    local tail_lines=${3:-50}
    
    if ! job_exists "$job_name"; then
        echo -e "${YELLOW}⚠ Job '$job_name' không tồn tại${NC}"
        return 1
    fi
    
    local status=$(kubectl get job -n "$NAMESPACE" "$job_name" -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}' 2>/dev/null || echo "False")
    local failed=$(kubectl get job -n "$NAMESPACE" "$job_name" -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}' 2>/dev/null || echo "False")
    
    local status_icon="❓"
    local status_color="$YELLOW"
    
    if [[ "$status" == "True" ]]; then
        status_icon="✅"
        status_color="$GREEN"
    elif [[ "$failed" == "True" ]]; then
        status_icon="❌"
        status_color="$RED"
    elif is_job_running "$job_name"; then
        status_icon="🔄"
        status_color="$CYAN"
    fi
    
    echo -e "${status_color}${status_icon} Job: ${BOLD}$job_name${NC}"
    
    local age=$(kubectl get job -n "$NAMESPACE" "$job_name" -o jsonpath='{.metadata.creationTimestamp}' 2>/dev/null)
    if [[ -n "$age" ]]; then
        echo -e "   ${BLUE}Created:${NC} $(echo "$age" | xargs -I {} date -d "{}" +"%Y-%m-%d %H:%M:%S" 2>/dev/null || echo "$age")"
    fi
    
    if [[ "$follow" == "true" ]] && is_job_running "$job_name"; then
        echo -e "   ${CYAN}Đang theo dõi real-time... (Ctrl+C để dừng)${NC}"
        kubectl logs -n "$NAMESPACE" "job/$job_name" -f
    else
        echo -e "   ${BLUE}Log (last $tail_lines lines):${NC}"
        kubectl logs -n "$NAMESPACE" "job/$job_name" --tail="$tail_lines" 2>/dev/null || echo -e "   ${YELLOW}Không có log hoặc job chưa chạy${NC}"
    fi
    echo ""
}

# Function: Show ML training summary
show_ml_summary() {
    local job_name="ml-train"
    
    if ! job_exists "$job_name"; then
        return
    fi
    
    print_subheader "ML Training Summary"
    
    # Extract key metrics
    local logs=$(kubectl logs -n "$NAMESPACE" "job/$job_name" 2>/dev/null || echo "")
    
    echo "$logs" | grep -E '(CV MAE|CV MAPE|CV MdAPE|Validation|Best|📈|TRAINING SUMMARY)' | tail -15 || true
}

# Function: Show ML predict summary  
show_predict_summary() {
    local job_name="ml-predict"
    
    if ! job_exists "$job_name"; then
        return
    fi
    
    print_subheader "ML Predict Summary"
    
    local logs=$(kubectl logs -n "$NAMESPACE" "job/$job_name" 2>/dev/null || echo "")
    
    echo "$logs" | grep -E '(forecast|predicted|saved|email|cold|ABC)' | tail -10 || true
}

# Function: Show ETL summary
show_etl_summary() {
    local job_name="spark-etl"
    
    if ! job_exists "$job_name"; then
        return
    fi
    
    print_subheader "ETL Summary"
    
    local logs=$(kubectl logs -n "$NAMESPACE" "job/$job_name" 2>/dev/null || echo "")
    
    echo "$logs" | grep -E '(Imported|Loaded|Processed|✅)' | tail -10 || true
}

# Function: Show DBT summary
show_dbt_summary() {
    local job_name="dbt-build"
    
    if ! job_exists "$job_name"; then
        return
    fi
    
    print_subheader "DBT Build Summary"
    
    local logs=$(kubectl logs -n "$NAMESPACE" "job/$job_name" 2>/dev/null || echo "")
    
    echo "$logs" | grep -E '(OK|SUCCESS|ERROR|Finished|models)' | tail -10 || true
}

# Function: Find most recent job
get_most_recent_job() {
    kubectl get jobs -n "$NAMESPACE" --sort-by=.metadata.creationTimestamp -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null | tail -1
}

# ============================================================
# MAIN EXECUTION
# ============================================================

# Show help if requested
[[ "$1" == "-h" || "$1" == "--help" ]] && show_help

# Check kubectl
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Lỗi:${NC} kubectl không được cài đặt"
    exit 1
fi

# Check namespace
if ! kubectl get namespace "$NAMESPACE" &>/dev/null; then
    echo -e "${RED}Lỗi:${NC} Namespace '$NAMESPACE' không tồn tại"
    exit 1
fi

# Handle specific job
if [[ -n "$SPECIFIC_JOB" ]]; then
    print_header "LOGS CHO JOB: $SPECIFIC_JOB"
    show_job_logs "$SPECIFIC_JOB" "$FOLLOW_MODE" 100
    
    # Show summary for ML jobs
    if [[ "$SPECIFIC_JOB" == "ml-train" ]]; then
        show_ml_summary
    elif [[ "$SPECIFIC_JOB" == "ml-predict" ]]; then
        show_predict_summary
    elif [[ "$SPECIFIC_JOB" == "spark-etl" ]]; then
        show_etl_summary
    elif [[ "$SPECIFIC_JOB" == "dbt-build" ]]; then
        show_dbt_summary
    fi
    
    exit 0
fi

# Handle last job only
if [[ "$SHOW_LAST" == "true" ]]; then
    LAST_JOB=$(get_most_recent_job)
    if [[ -n "$LAST_JOB" ]]; then
        print_header "JOB GẦN NHẤT: $LAST_JOB"
        show_job_logs "$LAST_JOB" "$FOLLOW_MODE" 100
    else
        echo -e "${RED}Không tìm thấy job nào${NC}"
        exit 1
    fi
    exit 0
fi

# Show all jobs
print_header "TẤT CẢ JOBS TRONG NAMESPACE: $NAMESPACE"

# List all jobs with status
echo ""
echo -e "${BOLD}Danh sách jobs:${NC}"
kubectl get jobs -n "$NAMESPACE" -o custom-columns=JOB:.metadata.name,STATUS:.status.conditions[0].type,COMPLETIONS:.status.succeeded,AGE:.metadata.creationTimestamp 2>/dev/null | head -20 || echo "Không có jobs"

# Spark ETL
print_header "1️⃣  SPARK ETL (CSV → PostgreSQL)"
show_job_logs "spark-etl" "$FOLLOW_MODE" 30
show_etl_summary

# Sync Data
print_header "2️⃣  SYNC DATA (PostgreSQL → ClickHouse)"
show_job_logs "sync-data" "$FOLLOW_MODE" 30

# DBT Build
print_header "3️⃣  DBT BUILD (Transformations)"
show_job_logs "dbt-build" "$FOLLOW_MODE" 30
show_dbt_summary

# ML Train
print_header "4️⃣  ML TRAINING (XGBoost + Optuna)"
show_job_logs "ml-train" "$FOLLOW_MODE" 50
show_ml_summary

# ML Predict
print_header "5️⃣  ML PREDICT (Forecasting)"
show_job_logs "ml-predict" "$FOLLOW_MODE" 30
show_predict_summary

# Summary
print_header "📊 TÓM TẮT"
echo ""
echo -e "${BOLD}Để xem chi tiết hơn:${NC}"
echo "  $0 -j ml-train --last    # Xem full log ml-train"
echo "  $0 -j ml-predict -f      # Theo dõi predict real-time"
echo "  $0 -f                    # Theo dõi tất cả jobs"
echo ""
echo -e "${GREEN}✅ Hoàn thành!${NC}"
