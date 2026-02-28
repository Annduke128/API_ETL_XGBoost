#!/bin/bash

# ============================================
# Auto-update K3s deployments from DockerHub
# ============================================
# This script checks for new images on DockerHub and updates deployments
# Usage: ./auto-update.sh [dockerhub-username]
# Can be run manually or as a CronJob in K3s

set -e

DOCKERHUB_USER=${1:-"your-dockerhub-username"}
NAMESPACE="hasu-ml"

echo "============================================"
echo "K3s Auto-Update from DockerHub"
echo "DockerHub User: $DOCKERHUB_USER"
echo "Namespace: $NAMESPACE"
echo "Time: $(date)"
echo "============================================"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Check kubectl
if ! command -v kubectl &> /dev/null; then
    log_error "kubectl not found!"
    exit 1
fi

# Function to update a deployment
update_deployment() {
    local name=$1
    local image=$2
    
    log_info "Checking $name..."
    
    # Get current image
    current_image=$(kubectl get deployment $name -n $NAMESPACE -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || echo "")
    
    if [ -z "$current_image" ]; then
        log_warn "Deployment $name not found, skipping..."
        return
    fi
    
    new_image="${DOCKERHUB_USER}/${image}:latest"
    
    if [ "$current_image" != "$new_image" ]; then
        log_info "Updating $name: $current_image -> $new_image"
        kubectl set image deployment/$name -n $NAMESPACE \
            $name=${new_image} --record
        kubectl rollout status deployment/$name -n $NAMESPACE --timeout=300s
        log_success "$name updated successfully!"
    else
        log_info "$name is up to date ($current_image)"
    fi
}

# Function to restart a deployment (force pull latest)
restart_deployment() {
    local name=$1
    
    log_info "Restarting $name to pull latest image..."
    kubectl rollout restart deployment/$name -n $NAMESPACE
    kubectl rollout status deployment/$name -n $NAMESPACE --timeout=300s
    log_success "$name restarted successfully!"
}

# Main update logic
echo ""
log_info "Starting update check..."

# Update ML Pipeline CronJobs (they use Always pull policy, just need restart)
log_info "Checking ML Pipeline CronJobs..."
kubectl get cronjob ml-training -n $NAMESPACE &>/dev/null && \
    kubectl patch cronjob ml-training -n $NAMESPACE -p '{"spec":{"suspend":false}}'
kubectl get cronjob ml-predict -n $NAMESPACE &>/dev/null && \
    kubectl patch cronjob ml-predict -n $NAMESPACE -p '{"spec":{"suspend":false}}'

# Force restart to pull latest images
restart_deployment "airflow-webserver" 2>/dev/null || log_warn "airflow-webserver not found"
restart_deployment "airflow-scheduler" 2>/dev/null || log_warn "airflow-scheduler not found"
restart_deployment "superset" 2>/dev/null || log_warn "superset not found"

echo ""
log_success "Auto-update completed at $(date)"

# Print current status
echo ""
echo "============================================"
echo "Current Deployment Status:"
echo "============================================"
kubectl get deployments -n $NAMESPACE -o wide 2>/dev/null || echo "No deployments found"

kubectl get cronjobs -n $NAMESPACE 2>/dev/null || echo "No cronjobs found"
