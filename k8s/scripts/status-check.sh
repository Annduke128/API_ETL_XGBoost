#!/bin/bash
# Script kiểm tra trạng thái K3s cluster

echo "====================================="
echo "K3s Cluster Status Check"
echo "====================================="

echo ""
echo "🖥️  NODES:"
echo "-------------------------------------"
kubectl get nodes -o wide

echo ""
echo "📦 PODS (all namespaces):"
echo "-------------------------------------"
kubectl get pods -A --sort-by='.metadata.namespace' | grep -v "Completed"

echo ""
echo "💾 STORAGE:"
echo "-------------------------------------"
echo "StorageClasses:"
kubectl get storageclass
echo ""
echo "PersistentVolumes:"
kubectl get pv
echo ""
echo "PersistentVolumeClaims:"
kubectl get pvc -A

echo ""
echo "🗄️  DATABASES:"
echo "-------------------------------------"
if kubectl get cluster -n database >/dev/null 2>&1; then
    echo "PostgreSQL Clusters:"
    kubectl get cluster -n database
    echo ""
    echo "PostgreSQL Pods:"
    kubectl get pods -n database -l app.kubernetes.io/name=postgresql
fi

echo ""
echo "📊 ML PIPELINE:"
echo "-------------------------------------"
kubectl get cronjob -n ml-pipeline 2>/dev/null || echo "No CronJobs found"
kubectl get jobs -n ml-pipeline 2>/dev/null || echo "No Jobs found"

echo ""
echo "🔧 RESOURCES USAGE:"
echo "-------------------------------------"
if kubectl top nodes >/dev/null 2>&1; then
    echo "Node Resources:"
    kubectl top nodes
    echo ""
    echo "Pod Resources:"
    kubectl top pods -A --sort-by='cpu' | head -20
else
    echo "Metrics server not available. Cài đặt bằng:"
    echo "  kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml"
fi

echo ""
echo "🌐 SERVICES:"
echo "-------------------------------------"
kubectl get svc -A | grep -v "ClusterIP.*none"

echo ""
echo "====================================="
echo "Status Check Complete"
echo "====================================="
