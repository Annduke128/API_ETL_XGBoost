#!/bin/bash
# Script build Docker images cho K3s
# Chạy trên 1 trong 2 node (hoặc máy khác có docker)

set -e

REGISTRY="${REGISTRY:-localhost:5000}"
VERSION="${VERSION:-latest}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "====================================="
echo "Building Docker Images for K3s"
echo "====================================="
echo "Registry: $REGISTRY"
echo "Version: $VERSION"
echo ""

# Hàm build image
build_image() {
    local name=$1
    local path=$2
    local dockerfile=$3
    
    echo "Building $name..."
    docker build -t $name:$VERSION -f $path/$dockerfile $path
    docker tag $name:$VERSION $REGISTRY/$name:$VERSION
    echo "✓ $name built"
}

# Build ML Pipeline
echo "1. Building ML Pipeline..."
build_image "retail-ml-pipeline" "$PROJECT_DIR/ml_pipeline" "Dockerfile"

# Build DBT
echo "2. Building DBT..."
build_image "retail-dbt" "$PROJECT_DIR/dbt_retail" "Dockerfile"

# Build Sync Tool
echo "3. Building Sync Tool..."
build_image "retail-sync-tool" "$PROJECT_DIR/data_cleaning" "Dockerfile"

echo ""
echo "====================================="
echo "Build Complete!"
echo "====================================="
echo ""
echo "Để push lên registry:"
echo "  docker push $REGISTRY/retail-ml-pipeline:$VERSION"
echo "  docker push $REGISTRY/retail-dbt:$VERSION"
echo "  docker push $REGISTRY/retail-sync-tool:$VERSION"
echo ""
echo "Hoặc sử dụng với K3s local (không cần push):"
echo "  k3s ctr images import <(docker save retail-ml-pipeline:$VERSION)"
