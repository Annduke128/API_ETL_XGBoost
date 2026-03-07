#!/bin/bash
set -e

DOCKERHUB_USER=${1:-$DOCKERHUB_USERNAME}
if [ -z "$DOCKERHUB_USER" ]; then
    echo "❌ Error: Docker Hub username required"
    echo "Usage: ./build-and-push-k3s.sh <dockerhub-username>"
    exit 1
fi

echo "🔨 Building images from root context..."

# Build từ root context với Dockerfile riêng cho từng service
docker build -f Dockerfile.sync-tool -t ${DOCKERHUB_USER}/hasu-sync-tool:latest .
docker build -f Dockerfile.ml-pipeline -t ${DOCKERHUB_USER}/hasu-ml-pipeline:latest .
docker build -f Dockerfile.spark-etl -t ${DOCKERHUB_USER}/hasu-spark-etl:latest .
docker build -f Dockerfile.dbt -t ${DOCKERHUB_USER}/hasu-dbt:latest .

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
