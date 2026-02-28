#!/bin/bash

# ============================================
# Build and Push Docker Images to DockerHub
# ============================================
# Usage: ./build-and-push.sh [dockerhub-username]
# Example: ./build-and-push.sh hasuadmin

set -e

DOCKERHUB_USER=${1:-"your-dockerhub-username"}
VERSION=${2:-"latest"}

echo "============================================"
echo "Building and Pushing Images"
echo "DockerHub User: $DOCKERHUB_USER"
echo "Version: $VERSION"
echo "============================================"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if logged in to DockerHub
if ! docker info | grep -q "Username"; then
    log_error "Not logged in to DockerHub!"
    echo "Please run: docker login"
    exit 1
fi

# Build từ root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

cd "$ROOT_DIR"

# Build ML Pipeline
echo ""
log_info "Building ML Pipeline image..."
docker build -t ${DOCKERHUB_USER}/hasu-ml-pipeline:${VERSION} \
    -f docker/ml_pipeline/Dockerfile .
docker tag ${DOCKERHUB_USER}/hasu-ml-pipeline:${VERSION} \
    ${DOCKERHUB_USER}/hasu-ml-pipeline:latest

# Build DBT
echo ""
log_info "Building DBT image..."
docker build -t ${DOCKERHUB_USER}/hasu-dbt:${VERSION} \
    -f docker/dbt_retail/Dockerfile .
docker tag ${DOCKERHUB_USER}/hasu-dbt:${VERSION} \
    ${DOCKERHUB_USER}/hasu-dbt:latest

# Build Sync Tool
echo ""
log_info "Building Sync Tool image..."
docker build -t ${DOCKERHUB_USER}/hasu-sync-tool:${VERSION} \
    -f docker/data_cleaning/Dockerfile .
docker tag ${DOCKERHUB_USER}/hasu-sync-tool:${VERSION} \
    ${DOCKERHUB_USER}/hasu-sync-tool:latest

echo ""
read -p "Push images to DockerHub? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "Pushing images..."
    
    docker push ${DOCKERHUB_USER}/hasu-ml-pipeline:${VERSION}
    docker push ${DOCKERHUB_USER}/hasu-ml-pipeline:latest
    
    docker push ${DOCKERHUB_USER}/hasu-dbt:${VERSION}
    docker push ${DOCKERHUB_USER}/hasu-dbt:latest
    
    docker push ${DOCKERHUB_USER}/hasu-sync-tool:${VERSION}
    docker push ${DOCKERHUB_USER}/hasu-sync-tool:latest
    
    log_success "All images pushed successfully!"
else
    log_info "Skipping push. Images built locally."
fi

echo ""
echo "============================================"
echo "Images:"
echo "  - ${DOCKERHUB_USER}/hasu-ml-pipeline:${VERSION}"
echo "  - ${DOCKERHUB_USER}/hasu-dbt:${VERSION}"
echo "  - ${DOCKERHUB_USER}/hasu-sync-tool:${VERSION}"
echo "============================================"
