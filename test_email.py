#!/usr/bin/env python3
"""
Test script để gửi email báo cáo dự báo thử nghiệm
Kiểm tra logo hiển thị đúng chưa
"""

import os
import sys
import pandas as pd
from datetime import datetime, timedelta

# Thêm ml_pipeline vào path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ml_pipeline'))

from email_notifier import EmailNotifier

def create_sample_forecasts():
    """Tạo dữ liệu mẫu cho test"""
    data = []
    base_date = datetime.now()
    
    # Tạo 50 sản phẩm mẫu
    products = [
        ("SP001", "Nước mắm Nam Ngư 500ml", "Gia vị", 150, 180),
        ("SP002", "Dầu ăn Simply 1L", "Gia vị", 200, 220),
        ("SP003", "Sữa Vinamilk 1L", "Sữa", 180, 200),
        ("SP004", "Mì Hảo Hảo gói", "Thực phẩm", 300, 320),
        ("SP005", "Coca Cola lon 330ml", "Nước giải khát", 250, 280),
        ("SP006", "Pepsi chai 1.5L", "Nước giải khát", 180, 200),
        ("SP007", "Bia Heineken lon", "Đồ uống có cồn", 120, 150),
        ("SP008", "Khăn giấy Pulppy", "Vệ sinh", 100, 120),
        ("SP009", "Dầu gội Head & Shoulders", "Chăm sóc cá nhân", 80, 100),
        ("SP010", "Sữa tắm Lifebuoy", "Chăm sóc cá nhân", 90, 110),
    ]
    
    # Tạo 50 sản phẩm
    for i in range(50):
        if i < len(products):
            code, name, category, last_week, predicted = products[i]
        else:
            code = f"SP{i+1:03d}"
            name = f"Sản phẩm test {i+1}"
            category = "Khác"
            last_week = 50 + (i * 2)
            predicted = 60 + (i * 2)
        
        # Tạo dữ liệu cho 7 ngày
        for day in range(7):
            date = base_date + timedelta(days=day)
            data.append({
                'ma_hang': code,
                'ten_san_pham': name,
                'nhom_hang_cap_1': category,
                'forecast_date': date.strftime('%Y-%m-%d'),
                'predicted_quantity': predicted // 7,
                'predicted_revenue': (predicted // 7) * 25000,
                'last_week_sales': last_week
            })
    
    return pd.DataFrame(data)

def create_sample_inventory():
    """Tạo dữ liệu tồn kho mẫu"""
    inventory = []
    for i in range(20):
        inventory.append({
            'product_code': f"SP{i+1:03d}",
            'product_name': f"Sản phẩm test {i+1}",
            'category': "Test",
            'predicted_7_days': 100 + (i * 10),
            'predicted_margin_pct': 15.5 + i,
            'safety_stock': 150 + (i * 15),
            'suggested_order_quantity': 200 + (i * 20),
            'reorder_urgency': 'High' if i < 5 else 'Normal'
        })
    return inventory

def main():
    print("=" * 60)
    print("🧪 TEST EMAIL FORECAST REPORT")
    print("=" * 60)
    
    # Kiểm tra logo file
    logo_path = os.getenv('HASU_LOGO_PATH', '/app/assets/hasu_logo.png')
    if os.path.exists(logo_path):
        print(f"✅ Logo found: {logo_path}")
        print(f"   Size: {os.path.getsize(logo_path)} bytes")
    else:
        print(f"⚠️ Logo not found at: {logo_path}")
        print(f"   Email will show text header instead")
    
    # Kiểm tra email config
    email_sender = os.getenv('EMAIL_SENDER', '')
    email_password = os.getenv('EMAIL_PASSWORD', '')
    
    print(f"\n📧 Email Sender: {email_sender or 'NOT SET'}")
    print(f"🔑 Email Password: {'*' * len(email_password) if email_password else 'NOT SET'}")
    
    if not email_sender or not email_password:
        print("\n❌ ERROR: EMAIL_SENDER and EMAIL_PASSWORD must be set in .env")
        print("   Please check your .env file")
        return 1
    
    # Tạo dữ liệu mẫu
    print("\n📊 Creating sample forecast data...")
    forecasts = create_sample_forecasts()
    inventory = create_sample_inventory()
    
    print(f"   Forecast records: {len(forecasts)}")
    print(f"   Inventory recommendations: {len(inventory)}")
    print(f"   Unique products: {forecasts['ma_hang'].nunique()}")
    
    # Gửi email
    print("\n📧 Sending test email...")
    notifier = EmailNotifier()
    
    # Kiểm tra recipients
    recipients = notifier._get_recipients('forecast_report')
    if not recipients:
        print("⚠️ No recipients configured for forecast_report")
        print("   Checking EMAIL_FORECAST_REPORT env var...")
        recipients = [email_sender]  # Fallback to sender
        print(f"   Using sender as recipient: {email_sender}")
    
    print(f"   Recipients: {recipients}")
    
    # Gửi email
    try:
        success = notifier.send_forecast_report(
            forecasts=forecasts,
            inventory_recommendations=inventory
        )
        
        if success:
            print("\n" + "=" * 60)
            print("✅ EMAIL SENT SUCCESSFULLY!")
            print("=" * 60)
            print(f"\n📬 Check your inbox: {recipients}")
            print("\n💡 What to check:")
            print("   1. Subject: 'BẢN DỰ BÁO DOANH SỐ HASU'")
            print("   2. Logo displays correctly at top")
            print("   3. Table has 50 products")
            print("   4. Columns: Tên SP, Danh mục, Bán tuần qua, Xu hướng, Tồn kho, Đề xuất")
            print("   5. Trends show 📈 📉 ➡️ icons")
        else:
            print("\n❌ Failed to send email")
            return 1
            
    except Exception as e:
        print(f"\n❌ Error sending email: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
