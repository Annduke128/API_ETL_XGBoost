#!/bin/bash
# =============================================================================
# Cài đặt NVIDIA Device Plugin cho K3s
# Cho phép Kubernetes nhận diện và sử dụng GPU
# =============================================================================

set -e

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║     CÀI ĐẶT NVIDIA DEVICE PLUGIN CHO K3S                             ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# Kiểm tra kubectl
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl không tìm thấy"
    exit 1
fi

echo "📋 1. Kiểm tra GPU trên worker node..."
echo "======================================"
echo "Chạy lệnh sau trên k3s-worker-gpu để kiểm tra:"
echo "  nvidia-smi"
echo ""
echo "Nếu chưa có nvidia-smi, cần cài đặt NVIDIA drivers trước:"
echo "  https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/"
echo ""

echo "📋 2. Cài đặt NVIDIA Device Plugin..."
echo "======================================"

# Cách 1: Dùng DaemonSet chính thức
echo "Cài đặt NVIDIA Device Plugin (DaemonSet)..."
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml

echo ""
echo "⏳ Đợi device plugin khởi động..."
sleep 10

echo ""
echo "📋 3. Kiểm tra installation..."
echo "=============================="
kubectl get pods -n kube-system -l name=nvidia-device-plugin-ds
echo ""

echo "📋 4. Verify GPU resources..."
echo "============================="
echo "Kiểm tra node capacity:"
kubectl describe node k3s-worker-gpu | grep -E "(nvidia.com/gpu|Capacity|Allocatable)"
echo ""

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║     HOÀN THÀNH!                                                      ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Sau khi cài đặt, node sẽ có capacity: nvidia.com/gpu: 1"
echo ""
echo "Kiểm tra: kubectl describe node k3s-worker-gpu | grep nvidia"
echo ""
