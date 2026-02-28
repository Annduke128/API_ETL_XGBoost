#!/bin/bash

# ============================================
# Check K3s cluster status
# ============================================

NAMESPACE="hasu-ml"

echo "============================================"
echo "K3s Cluster Status"
echo "Time: $(date)"
echo "============================================"

echo ""
echo "=== Nodes ==="
kubectl get nodes -o wide

echo ""
echo "=== Namespace Resource Usage ==="
kubectl top nodes 2>/dev/null || echo "Metrics not available"

echo ""
echo "=== Deployments ($NAMESPACE) ==="
kubectl get deployments -n $NAMESPACE -o wide

echo ""
echo "=== Pods ($NAMESPACE) ==="
kubectl get pods -n $NAMESPACE -o wide

echo ""
echo "=== Services ($NAMESPACE) ==="
kubectl get services -n $NAMESPACE

echo ""
echo "=== CronJobs ($NAMESPACE) ==="
kubectl get cronjobs -n $NAMESPACE

echo ""
echo "=== PVCs ($NAMESPACE) ==="
kubectl get pvc -n $NAMESPACE

echo ""
echo "=== Recent Events ==="
kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp' | tail -10
