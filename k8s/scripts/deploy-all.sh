#!/bin/bash

# ============================================
# Deploy all K3s resources
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================"
echo "Deploying Hasu ML to K3s"
echo "============================================"

# Check kubectl
if ! command -v kubectl &>/dev/null; then
    echo "ERROR: kubectl not found!"
    exit 1
fi

# Check k3s
if ! kubectl cluster-info &>/dev/null; then
    echo "ERROR: K3s cluster not accessible!"
    exit 1
fi

echo ""
echo "Step 1/6: Creating namespace..."
kubectl apply -f $K8S_DIR/00-namespace/

echo ""
echo "Step 2/6: Creating storage..."
kubectl apply -f $K8S_DIR/01-storage/

echo ""
echo "Step 3/6: Creating configmaps..."
kubectl apply -f $K8S_DIR/02-config/configmap.yaml
kubectl apply -f $K8S_DIR/02-config/postgres-init-configmap.yaml 2>/dev/null || true

echo ""
echo "Step 4/6: Creating databases..."
kubectl apply -f $K8S_DIR/03-databases/

echo ""
echo "Step 5/6: Creating applications..."
kubectl apply -f $K8S_DIR/04-applications/

echo ""
echo "Step 6/6: Creating ML pipeline and DBT jobs..."
kubectl apply -f $K8S_DIR/05-ml-pipeline/

# Không chạy dbt-run job ngay (để user chạy thủ công)
kubectl delete job dbt-run -n hasu-ml 2>/dev/null || true

echo ""
echo "============================================"
echo "Deployment completed!"
echo "============================================"
echo ""
echo "Check status:"
echo "  kubectl get all -n hasu-ml"
echo ""
echo "Port forward for local access:"
echo "  kubectl port-forward svc/airflow 8080:8080 -n hasu-ml"
echo "  kubectl port-forward svc/superset 8088:8088 -n hasu-ml"
