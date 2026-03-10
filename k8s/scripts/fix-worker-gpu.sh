#!/bin/bash
# =============================================================================
# Script kích hoạt lại k3s-worker-gpu node
# Chạy script này TRỰC TIẾP trên worker node (SSH vào k3s-worker-gpu)
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     KÍCH HOẠT LẠI K3S WORKER GPU NODE                                ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Kiểm tra xem có phải đang chạy trên worker node không
if [[ "$(hostname)" != "k3s-worker-gpu" ]]; then
    echo -e "${YELLOW}⚠️  Cảnh báo: Script này đang chạy trên $(hostname)${NC}"
    echo "Script này cần chạy TRỰC TIẾP trên k3s-worker-gpu node"
    echo ""
    echo "Hãy SSH vào worker node trước:"
    echo "  ssh user@192.168.102.29"
    echo "  sudo bash fix-worker-gpu.sh"
    echo ""
    read -p "Bạn có muốn tiếp tục không? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        echo "Đã hủy."
        exit 1
    fi
fi

echo -e "${YELLOW}🔍 Bước 1: Kiểm tra trạng thái k3s-agent...${NC}"
if systemctl is-active --quiet k3s-agent; then
    echo -e "${GREEN}✓ k3s-agent đang chạy${NC}"
else
    echo -e "${RED}✗ k3s-agent đã dừng${NC}"
fi

echo ""
echo -e "${YELLOW}🔍 Bước 2: Kiểm tra logs gần đây...${NC}"
journalctl -u k3s-agent --no-pager -n 20 2>/dev/null || echo "Không thể đọc logs"

echo ""
echo -e "${YELLOW}🔧 Bước 3: Kiểm tra kết nối đến master...${NC}"
MASTER_IP="192.168.102.17"
if ping -c 1 $MASTER_IP &> /dev/null; then
    echo -e "${GREEN}✓ Kết nối đến master ($MASTER_IP) OK${NC}"
else
    echo -e "${RED}✗ Không thể kết nối đến master ($MASTER_IP)${NC}"
fi

echo ""
echo -e "${YELLOW}🔧 Bước 4: Kiểm tra và restart k3s-agent...${NC}"
echo "Dừng k3s-agent (nếu đang chạy)..."
sudo systemctl stop k3s-agent 2>/dev/null || true
sleep 2

echo "Dọn dẹp container cũ (nếu có)..."
sudo k3s-killall.sh 2>/dev/null || true
sleep 2

echo "Khởi động lại k3s-agent..."
sudo systemctl start k3s-agent
sleep 5

echo ""
echo -e "${YELLOW}🔍 Bước 5: Kiểm tra trạng thái sau restart...${NC}"
if systemctl is-active --quiet k3s-agent; then
    echo -e "${GREEN}✓ k3s-agent đã khởi động thành công!${NC}"
    sudo systemctl status k3s-agent --no-pager
else
    echo -e "${RED}✗ k3s-agent khởi động thất bại!${NC}"
    echo "Logs lỗi:"
    sudo journalctl -u k3s-agent --no-pager -n 50
    exit 1
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     HOÀN THÀNH!                                                      ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "K3s-agent đã được restart. Node sẽ trở lại Ready trong vòng 30-60 giây."
echo ""
echo "Kiểm tra trên master node:"
echo "  kubectl get nodes"
echo ""
