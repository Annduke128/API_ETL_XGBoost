#!/bin/bash
# Script cài đặt K3s Master Node
# Chạy trên máy Master (192.168.1.101)

set -e

MASTER_IP="192.168.1.101"
NODE_NAME="k3s-master"

echo "====================================="
echo "Installing K3s Master Node"
echo "====================================="

# 1. Cấu hình hostname
sudo hostnamectl set-hostname $NODE_NAME

# 2. Cấu hình /etc/hosts
cat <<EOF | sudo tee /etc/hosts
127.0.0.1 localhost
$MASTER_IP $NODE_NAME
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
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
EOF
sudo sysctl --system

# 6. Install K3s
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=v1.28.5+k3s1 sh -s - server \
    --cluster-init \
    --tls-san $MASTER_IP \
    --disable traefik \
    --disable servicelb \
    --kube-proxy-arg "ipvs-strict-arp=true" \
    --kubelet-arg "feature-gates=CSINodeExpandSecret=true"

# 7. Đợi K3s sẵn sàng
echo "Waiting for K3s to be ready..."
sleep 30
sudo systemctl status k3s --no-pager

# 8. Cấu hình kubectl cho user hiện tại
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config
chmod 600 ~/.kube/config

# 9. Export KUBECONFIG
echo 'export KUBECONFIG=~/.kube/config' >> ~/.bashrc
export KUBECONFIG=~/.kube/config

# 10. Kiểm tra cluster
echo "====================================="
echo "K3s Master Node Installed!"
echo "====================================="
echo ""
echo "Node status:"
kubectl get nodes -o wide
echo ""
echo "Pod status:"
kubectl get pods -n kube-system
echo ""
echo "TOKEN for worker nodes:"
sudo cat /var/lib/rancher/k3s/server/token
echo ""
echo "====================================="
echo "Next steps:"
echo "1. Lưu token ở trên"
echo "2. Cài đặt Helm: make install-helm"
echo "3. Cài đặt Longhorn: make install-longhorn"
echo "4. Chạy script install-k3s-worker.sh trên máy Worker"
echo "====================================="
