#!/bin/bash
# Script tự động xử lý CSV files

cd "$(dirname "$0")"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Retail CSV Auto Processor ===${NC}"
echo ""

# Check if container is running
if docker-compose ps | grep -q "retail_csv_watcher"; then
    echo -e "${YELLOW}CSV Watcher đang chạy. Đang xử lý files...${NC}"
    docker-compose exec csv-watcher python auto_process_csv.py --input /csv_input --output /csv_output
else
    echo -e "${GREEN}Khởi động CSV Processor một lần...${NC}"
    
    # Run one-time processor
    docker-compose run --rm --name retail_csv_processor \
        -v "$(pwd)/csv_input:/csv_input" \
        -v "$(pwd)/csv_output:/csv_output" \
        csv-watcher \
        python auto_process_csv.py --input /csv_input --output /csv_output
fi

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ Xử lý hoàn tất thành công!${NC}"
else
    echo -e "${RED}❌ Có lỗi xảy ra!${NC}"
fi

exit $EXIT_CODE
