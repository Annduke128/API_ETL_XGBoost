"""
Product Name Parser Module
Tách tên sản phẩm thành các thành phần: clean_name, weight, unit, packaging_type

Usage:
    from product_parser import parse_product_name, parse_product_dataframe
    
    # Parse single name
    clean_name, weight, unit, pack_type = parse_product_name("OMO 700g (Gói)")
    
    # Parse DataFrame
    df = parse_product_dataframe(df, name_column='Tên hàng')
"""

import re
from typing import Tuple, Optional, TYPE_CHECKING

# Import pandas chỉ khi cần
if TYPE_CHECKING:
    import pandas as pd


def parse_product_name(product_name: str) -> Tuple[Optional[str], Optional[float], Optional[str], Optional[str]]:
    """
    Parse tên sản phẩm để tách weight và packaging info
    
    Logic 3 bước:
    1. Pack info trong ngoặc () → packaging_type
    2. Weight có đơn vị đo (g, kg, ml, l) → weight + unit  
    3. Còn lại → clean_name
    
    Args:
        product_name: Tên sản phẩm gốc
        
    Returns:
        Tuple của (clean_name, weight, unit, packaging_type)
        
    Examples:
        >>> parse_product_name("OMO Bột Giặt 700g (Gói)")
        ('OMO Bột Giặt', 700.0, 'g', 'Gói')
        
        >>> parse_product_name("Cung Đình mì (12 thố)")
        ('Cung Đình mì', None, None, '12 thố')
    """
    # Check None or NaN (from pandas/numpy) or empty string
    if product_name is None:
        return None, None, None, None
    
    # Handle pandas/numpy NaN if present
    try:
        import pandas as pd
        if pd.isna(product_name):
            return None, None, None, None
    except ImportError:
        pass
    
    if not product_name:
        return None, None, None, None
    
    original = str(product_name).strip()
    remaining = original
    
    # === BƯỚC 1: Extract pack info TRONG NGOẶC () ===
    packaging_type = None
    pack_pattern = r'\s*\(([^)]+)\)\s*$'
    pack_match = re.search(pack_pattern, remaining)
    
    if pack_match:
        packaging_type = pack_match.group(1).strip()
        remaining = remaining[:pack_match.start()]
    
    # === BƯỚC 2: Extract weight (số có đơn vị đo) ===
    weight = None
    unit = None
    # Pattern: số + đơn vị đo (chấp nhận cả . và , làm decimal)
    weight_pattern = r'(\d+(?:[.,]\d+)?)\s*(g|kg|ml|l|L)\b'
    weight_match = re.search(weight_pattern, remaining, re.IGNORECASE)
    
    if weight_match:
        weight_str = weight_match.group(1).replace(',', '.')
        weight = float(weight_str)
        unit = weight_match.group(2).lower()
        unit = 'l' if unit == 'L' else unit
        remaining = remaining[:weight_match.start()] + remaining[weight_match.end():]
    
    # === BƯỚC 3: Clean ===
    clean_name = re.sub(r'\s+', ' ', remaining).strip()
    clean_name = clean_name.rstrip('. ')
    
    return clean_name, weight, unit, packaging_type


def parse_product_dataframe(df, name_column: str = 'ten_hang'):
    """
    Parse tên sản phẩm cho toàn bộ DataFrame
    
    Args:
        df: DataFrame chứa cột tên sản phẩm
        name_column: Tên cột chứa tên sản phẩm
        
    Returns:
        DataFrame với các cột mới: clean_name, weight, unit, packaging_type
    """
    import pandas as pd
    df = df.copy()
    
    # Parse tất cả tên sản phẩm
    parsed = df[name_column].apply(parse_product_name)
    
    df['clean_name'] = [x[0] for x in parsed]
    df['weight'] = [x[1] for x in parsed]
    df['unit'] = [x[2] for x in parsed]
    df['packaging_type'] = [x[3] for x in parsed]
    
    return df


def get_parsing_stats(df) -> dict:
    """
    Lấy thống kê về kết quả parsing
    
    Args:
        df: DataFrame đã được parse (có clean_name, weight, unit, packaging_type)
        
    Returns:
        Dict chứa thống kê
    """
    total = len(df)
    has_weight = df['weight'].notna().sum()
    has_packaging = df['packaging_type'].notna().sum()
    has_both = (df['weight'].notna() & df['packaging_type'].notna()).sum()
    
    return {
        'total': total,
        'has_weight': has_weight,
        'has_weight_pct': round(has_weight / total * 100, 1) if total > 0 else 0,
        'has_packaging': has_packaging,
        'has_packaging_pct': round(has_packaging / total * 100, 1) if total > 0 else 0,
        'has_both': has_both,
        'has_both_pct': round(has_both / total * 100, 1) if total > 0 else 0,
    }


# For testing
if __name__ == '__main__':
    # Test cases
    test_cases = [
        "OMO Bột Giặt Comfort 700g (Gói)",
        "Cung Đình mì khoai tây hương vị Gà hầm (12 thố)",
        "Bim Bim Que Tăm Đậu 0,35Kg (Gói)",
        "NESCAFE 3in1 Rang Dam Hop 24 16g (Hộp)",
        "Khẩu trang 5D (Thùng/100c)",
    ]
    
    print("=== Product Parser Test ===\n")
    for name in test_cases:
        clean, w, u, p = parse_product_name(name)
        print(f"Input:  {name}")
        print(f"        → Clean: '{clean}'")
        print(f"        → Weight: {w} {u}")
        print(f"        → Packaging: {p}")
        print()
