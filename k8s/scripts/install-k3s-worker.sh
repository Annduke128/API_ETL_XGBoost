#!/bin/bash
# Script cài đặt K3s Worker Node
# Chạy trên máy Worker (192.168.1.102)

set -e

MASTER_IP="192.168.1.101"
WORKER_IP="192.168.1.102"
NODE_NAME="k3s-worker"

echo "====================================="
echo "Installing K3s Worker Node"
echo "====================================="

# Kiểm tra token
if [ -z "$K3S_TOKEN" ]; then
    echo "ERROR: Vui lòng set K3S_TOKEN environment variable"
    echo "Lấy token từ master: sudo cat /var/lib/rancher/k3s/server/token"
    exit 1
fi

# 1. Cấu hình hostname
sudo hostnamectl set-hostname $NODE_NAME

# 2. Cấu hình /etc/hosts
cat <<EOF | sudo tee /etc/hosts
127.0.0.1 localhost
$MASTER_IP k3s-master
$WORKER_IP $NODE_NAME
EOF

# 3. Disable swap
sudo swapoff -a
sudo sed -i '/swap/d' /etc/fstab

# 4. Load kernel modules
sudo modprobe iscsi_tcp
sudo modprobe dm_snapshot
sudo modprobe dm_mirror
sudo modprobe dm_thin_pool

cat <<EOF | sudo tee /etc/modules-load.d/k3s.conf
iscsi_tcp
dm_snapshot
dm_mirror
dm_thin_pool
EOF

# 5. Cấu hình sysctl
cat <<EOF | sudo tee /etc/sysctl.d/99-k3s.conf
vm.max_map_count = 262144
vm.overcommit_memory = 1
net.ipv4.ip_forward = 1
EOF
sudo sysctl --system

# 6. Install K3s Agent
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=v1.28.5+k3s1 sh -s - agent \
    --server https://$MASTER_IP:6443 \
    --token $K3S_TOKEN

# 7. Đợi K3s sẵn sàng
echo "Waiting for K3s agent to be ready..."
sleep 10
sudo systemctl status k3s-agent --no-pager

echo "====================================="
echo "K3s Worker Node Installed!"
echo "====================================="
echo ""
echo "Kiểm tra trên Master node:"
echo "kubectl get nodes"
