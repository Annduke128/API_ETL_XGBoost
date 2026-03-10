#!/bin/bash
# Fix PVC access mode from ReadWriteMany to ReadWriteOnce

echo "🔧 Fixing PVC access mode..."

cat > /home/hasu/actions-runner/_work/API_ETL_XGBoost/API_ETL_XGBoost/k8s/spark/01-storage.yaml << 'YAML'
# Spark checkpoint directory
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: spark-checkpoint-pvc
  namespace: spark
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-storage
  resources:
    requests:
      storage: 20Gi
---
# Shared volume for data exchange between Spark and Python
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: spark-shared-pvc
  namespace: spark
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-storage
  resources:
    requests:
      storage: 50Gi
YAML

echo "✅ PVC access mode fixed: ReadWriteOnce"
grep "accessModes" /home/hasu/actions-runner/_work/API_ETL_XGBoost/API_ETL_XGBoost/k8s/spark/01-storage.yaml
