#!/usr/bin/env python3
"""
Script sửa product theo logic V2 - Rõ ràng:
1. Pack info → Trong () ở cuối
2. Weight → Số có đơn vị đo (g, kg, ml, l)
3. Còn lại → Tất cả vào tên
"""

import csv
import re

def parse_product_name_v2(product_name):
    """
    Logic 3 bước đơn giản:
    1. Xóa pack info trong ()
    2. Extract weight
    3. Còn lại là clean name
    """
    if not product_name:
        return None, None, None, None, None
    
    original = product_name.strip()
    remaining = original
    
    # === BƯỚC 1: Extract pack info trong () ở cuối ===
    pack_size = None
    packaging_type = None
    
    pack_pattern = r'\s*\(([^)]+)\)\s*$'
    pack_match = re.search(pack_pattern, remaining)
    
    if pack_match:
        pack_content = pack_match.group(1).strip()
        
        # KHÔNG tìm số để tách pack_size nữa
        # Toàn bộ nội dung trong ngoặc là packaging_type
        packaging_type = pack_content
        
        remaining = remaining[:pack_match.start()]
    
    # === BƯỚC 2: Extract weight ===
    weight = None
    unit = None
    
    weight_pattern = r'(\d+(?:[.,]\d+)?)\s*(g|kg|ml|l|L)\b'
    weight_match = re.search(weight_pattern, remaining, re.IGNORECASE)
    
    if weight_match:
        weight_str = weight_match.group(1).replace(',', '.')
        weight = float(weight_str)
        unit = weight_match.group(2).lower()
        remaining = remaining[:weight_match.start()] + remaining[weight_match.end():]
    
    # === BƯỚC 3: Clean ===
    clean_name = re.sub(r'\s+', ' ', remaining).strip()
    
    return clean_name, weight, unit, pack_size, packaging_type

def process_csv(input_file, output_file):
    """Xử lý file CSV"""
    print(f"Đọc file: {input_file}")
    
    results = []
    
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for idx, row in enumerate(reader):
            product_name = row.get('Tên sản phẩm', '')
            category = row.get('Ngành hàng', '')
            
            name, w, u, ps, pt = parse_product_name_v2(product_name)
            
            results.append({
                'original_name': product_name,
                'clean_name': name,
                'category': category,
                'weight': w if w else '',
                'unit': u if u else '',
                'pack_size': ps if ps else '',
                'packaging_type': pt if pt else ''
            })
            
            if idx < 10:
                print(f"\n{idx+1}. {product_name}")
                print(f"   → Clean: {name}")
                print(f"   → Weight: {w} {u}")
                print(f"   → Packaging: {pt}")
    
    # Ghi file
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['original_name', 'clean_name', 'category', 'weight', 'unit', 'pack_size', 'packaging_type'])
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\n✅ Đã lưu: {output_file}")
    print(f"Tổng: {len(results)} sản phẩm")
    
    # Thống kê
    has_weight = sum(1 for r in results if r['weight'])
    has_pack = sum(1 for r in results if r['packaging_type'])
    has_both = sum(1 for r in results if r['weight'] and r['packaging_type'])
    
    print(f"\n📊 Thống kê:")
    print(f"   - Có weight: {has_weight}")
    print(f"   - Có packaging type: {has_pack}")
    print(f"   - Có cả weight và packaging: {has_both}")
    
    return results

if __name__ == '__main__':
    process_csv(
        'product_edge_cases_inventory_fixed (full).csv',
        'product_edge_cases_inventory_V2.csv'
    )
    print("\n✅ Hoàn thành!")
