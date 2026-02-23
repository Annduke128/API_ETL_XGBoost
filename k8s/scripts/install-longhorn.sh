#!/bin/bash
# Script cài đặt Longhorn trên K3s

set -e

echo "====================================="
echo "Installing Longhorn"
echo "====================================="

# Tạo namespace
kubectl create namespace longhorn-system --dry-run=client -o yaml | kubectl apply -f -

# Cài đặt Longhorn
helm install longhorn longhorn/longhorn \
    --namespace longhorn-system \
    --set defaultSettings.defaultDataPath="/var/lib/longhorn" \
    --set defaultSettings.storageOverProvisioningPercentage=100 \
    --set defaultSettings.storageMinimalAvailablePercentage=10 \
    --set defaultSettings.replicaCount=2 \
    --set persistence.defaultClass=true \
    --set persistence.defaultClassReplicaCount=2

# Đợi Longhorn sẵn sàng
echo "Waiting for Longhorn to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/longhorn-driver-deployer -n longhorn-system
kubectl wait --for=condition=available --timeout=300s deployment/longhorn-ui -n longhorn-system

echo "====================================="
echo "Longhorn Installed!"
echo "====================================="
echo ""
echo "Truy cập Longhorn UI:"
echo "kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80"
echo "URL: http://localhost:8080"
echo ""
echo "StorageClass:"
kubectl get storageclass
