#!/bin/bash
set -e

DOCKERHUB_USER=${1:-$DOCKERHUB_USERNAME}
if [ -z "$DOCKERHUB_USER" ]; then
    echo "❌ Error: Docker Hub username required"
    echo "Usage: ./build-and-push-k3s.sh <dockerhub-username>"
    exit 1
fi

echo "🔨 Building images..."

# Build từng service với context và Dockerfile đúng
docker build -t ${DOCKERHUB_USER}/hasu-sync-tool:latest ./data_cleaning
docker build -t ${DOCKERHUB_USER}/hasu-ml-pipeline:latest ./ml_pipeline
docker build -t ${DOCKERHUB_USER}/hasu-spark-etl:latest ./spark-etl
docker build -t ${DOCKERHUB_USER}/hasu-dbt:latest ./dbt_retail

echo "⬆️ Pushing to Docker Hub..."
docker push ${DOCKERHUB_USER}/hasu-sync-tool:latest
docker push ${DOCKERHUB_USER}/hasu-ml-pipeline:latest
docker push ${DOCKERHUB_USER}/hasu-spark-etl:latest
docker push ${DOCKERHUB_USER}/hasu-dbt:latest

echo "✅ Done! All images pushed to Docker Hub"
echo ""
echo "Images:"
echo "  - ${DOCKERHUB_USER}/hasu-sync-tool:latest"
echo "  - ${DOCKERHUB_USER}/hasu-ml-pipeline:latest"
echo "  - ${DOCKERHUB_USER}/hasu-spark-etl:latest"
echo "  - ${DOCKERHUB_USER}/hasu-dbt:latest"
