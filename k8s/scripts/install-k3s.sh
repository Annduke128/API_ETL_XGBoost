#!/bin/bash

# ============================================
# Install K3s
# ============================================

set -e

echo "============================================"
echo "Installing K3s"
echo "============================================"

# Detect architecture
ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then
    ARCH="amd64"
fi

# Install K3s
echo "Installing K3s server..."
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --disable traefik" sh -

# Wait for K3s to be ready
echo "Waiting for K3s to be ready..."
sleep 10

# Copy kubeconfig
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
chmod 600 ~/.kube/config

# Export KUBECONFIG
echo 'export KUBECONFIG=~/.kube/config' >> ~/.bashrc
export KUBECONFIG=~/.kube/config

# Wait for node to be ready
echo "Waiting for node to be ready..."
kubectl wait --for=condition=Ready node --all --timeout=300s

echo ""
echo "============================================"
echo "K3s installed successfully!"
echo "============================================"
echo ""
echo "Check status:"
echo "  kubectl get nodes"
echo "  kubectl get pods -A"
