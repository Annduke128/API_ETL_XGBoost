#!/usr/bin/env python3
"""
Script parse product name - Sử dụng product_parser module

Logic 3 bước:
1. Pack info trong ngoặc () → packaging_type
2. Weight có đơn vị đo → weight + unit
3. Còn lại → clean_name

Usage:
    python fix_product_edge_cases.py [input_file] [output_file]
    
    Default:
    - Input: product_edge_cases_inventory_fixed (full).csv
    - Output: product_edge_cases_inventory_V2.csv
"""

import csv
import sys
import os

# Import from data_cleaning module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'data_cleaning'))
from product_parser import parse_product_name, get_parsing_stats


def process_csv(input_file, output_file):
    """Process CSV file với logic parse"""
    
    stats = {
        'total': 0,
        'has_weight': 0,
        'has_packaging': 0,
        'both': 0
    }
    
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = ['original_name', 'clean_name', 'weight', 'unit', 'packaging_type']
        
        rows = []
        for row in reader:
            stats['total'] += 1
            original = row.get('Tên sản phẩm', row.get('original_name', '')).strip()
            
            if not original:
                continue
            
            clean_name, weight, unit, packaging_type = parse_product_name(original)
            
            if weight is not None:
                stats['has_weight'] += 1
            if packaging_type is not None:
                stats['has_packaging'] += 1
            if weight is not None and packaging_type is not None:
                stats['both'] += 1
            
            rows.append({
                'original_name': original,
                'clean_name': clean_name,
                'weight': weight,
                'unit': unit,
                'packaging_type': packaging_type
            })
    
    # Write output
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    return stats


def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else 'product_edge_cases_inventory_fixed (full).csv'
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'product_edge_cases_inventory_V2.csv'
    
    print("=" * 60)
    print("🔧 Product Name Parser - Using product_parser module")
    print("=" * 60)
    
    stats = process_csv(input_file, output_file)
    
    print(f"\n✅ Đã xử lý: {stats['total']} sản phẩm")
    print(f"   - Có weight: {stats['has_weight']} ({stats['has_weight']/stats['total']*100:.1f}%)")
    print(f"   - Có packaging_type: {stats['has_packaging']} ({stats['has_packaging']/stats['total']*100:.1f}%)")
    print(f"   - Có cả hai: {stats['both']} ({stats['both']/stats['total']*100:.1f}%)")
    print(f"\n📁 Output: {output_file}")
    
    # Show some examples
    print("\n" + "=" * 60)
    print("📝 Một số ví dụ:")
    print("=" * 60)
    
    examples = [
        "OMO Bột Giặt Comfort 700g (Gói)",
        "Cung Đình mì khoai tây hương vị Gà hầm (12 thố)",
        "Cung Đình mì khoai tây hương vị Gà hầm 12 thố (Bát)",
        "Bim Bim Que Tăm Đậu 0,35Kg (Gói)",
        "NESCAFE 3in1 Rang Dam Hop 24 16g (Hộp)",
    ]
    
    for ex in examples:
        clean, w, u, pt = parse_product_name(ex)
        print(f"\nInput:  {ex}")
        print(f"        → Clean: '{clean}'")
        print(f"        → Weight: {w} {u}")
        print(f"        → Packaging: {pt}")


if __name__ == '__main__':
    main()
