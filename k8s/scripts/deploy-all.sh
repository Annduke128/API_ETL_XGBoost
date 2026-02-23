#!/bin/bash
# Script deploy toàn bộ ứng dụng lên K3s cluster
# Chạy sau khi đã cài đặt K3s, Longhorn, Helm

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$(dirname "$SCRIPT_DIR")"

echo "====================================="
echo "Deploying Retail Data Pipeline to K3s"
echo "====================================="

# 1. Kiểm tra K3s đã sẵn sàng
echo "Checking K3s status..."
kubectl get nodes || { echo "K3s not ready!"; exit 1; }

# 2. Tạo namespaces
echo "Creating namespaces..."
kubectl apply -f $K8S_DIR/00-namespaces/

# 3. Cấu hình Storage
echo "Setting up storage..."
kubectl apply -f $K8S_DIR/01-storage/

# 4. Tạo ConfigMaps và Secrets (kiểm tra secrets đã tồn tại)
echo "Creating configs..."
kubectl apply -f $K8S_DIR/02-config/configmap-retail.yaml

if ! kubectl get secret retail-secrets -n retail-data >/dev/null 2>&1; then
    echo "WARNING: retail-secrets chưa được tạo!"
    echo "Hãy chạy: kubectl apply -f $K8S_DIR/02-config/secrets.yaml"
    echo "(Copy từ secrets-template.yaml và đổi mật khẩu)"
fi

# 5. Cài đặt CloudNativePG (PostgreSQL)
echo "Installing CloudNativePG..."
if ! kubectl get deployment cnpg-controller-manager -n cnpg-system >/dev/null 2>&1; then
    kubectl apply --server-side -f https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.22/releases/cnpg-1.22.0.yaml
    echo "Waiting for CloudNativePG..."
    kubectl wait --for=condition=available --timeout=120s deployment/cnpg-controller-manager -n cnpg-system
fi

# 6. Cài đặt PostgreSQL Cluster
echo "Creating PostgreSQL cluster..."
kubectl apply -f $K8S_DIR/03-databases/postgres-cluster.yaml

# 7. Cài đặt Redis
echo "Installing Redis..."
helm upgrade --install redis bitnami/redis \
    -n retail-data \
    -f $K8S_DIR/03-databases/redis-values.yaml \
    --wait

# 8. Cài đặt ML Pipeline
echo "Setting up ML Pipeline..."
kubectl apply -f $K8S_DIR/05-ml-pipeline/

# 9. Cài đặt Monitoring (tùy chọn)
read -p "Cài đặt Prometheus + Grafana? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Installing Prometheus + Grafana..."
    helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
        -n monitoring \
        -f $K8S_DIR/06-monitoring/prometheus-values.yaml \
        --create-namespace \
        --wait
fi

echo ""
echo "====================================="
echo "Deployment Complete!"
echo "====================================="
echo ""
echo "Kiểm tra trạng thái:"
echo "  kubectl get pods -A"
echo ""
echo "PostgreSQL cluster:"
echo "  kubectl get cluster -n database"
echo ""
echo "ML Pipeline CronJobs:"
echo "  kubectl get cronjob -n ml-pipeline"
