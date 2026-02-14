#!/usr/bin/env python3
"""
Script kiểm tra cấu hình email và gửi email test
"""

import os
import sys
import argparse
from email_notifier import get_notifier


def check_environment():
    """Kiểm tra các biến môi trường cần thiết"""
    print("=" * 60)
    print("🔍 KIỂM TRA CẤU HÌNH EMAIL")
    print("=" * 60)
    
    # Kiểm tra EMAIL_PASSWORD
    email_password = os.getenv('EMAIL_PASSWORD', '')
    if not email_password:
        print("❌ EMAIL_PASSWORD chưa được thiết lập")
        print("\n📋 Hướng dẫn thiết lập EMAIL_PASSWORD:")
        print("1. Nếu sử dụng Gmail:")
        print("   - Bật 2-Factor Authentication trong tài khoản Google")
        print("   - Truy cập: https://myaccount.google.com/apppasswords")
        print("   - Tạo App Password cho 'Mail' > 'Other'")
        print("   - Copy 16 ký tự vào biến môi trường EMAIL_PASSWORD")
        print("\n2. Thiết lập biến môi trường:")
        print("   export EMAIL_PASSWORD='your-app-password'")
        return False
    else:
        masked = '*' * (len(email_password) - 4) + email_password[-4:] if len(email_password) > 4 else '****'
        print(f"✅ EMAIL_PASSWORD: {masked}")
    
    # Kiểm tra EMAIL_SENDER
    email_sender = os.getenv('EMAIL_SENDER', 'ml-pipeline@company.com')
    print(f"✅ EMAIL_SENDER: {email_sender}")
    
    return True


def check_config():
    """Kiểm tra file config"""
    print("\n" + "=" * 60)
    print("📄 KIỂM TRA FILE CONFIG")
    print("=" * 60)
    
    try:
        notifier = get_notifier()
        config = notifier.config
        
        # Kiểm tra recipients theo loại báo cáo
        print("\n📧 Phân quyền ngườ i nhận theo loại báo cáo:")
        print("-" * 50)
        
        report_types = ['training_report', 'forecast_report', 'error_alert']
        has_recipients = False
        placeholder_found = False
        
        for report_type in report_types:
            # Đọc từ config gốc để kiểm tra placeholder
            raw_recipients = []
            recipients_config = config.get('recipients', {})
            by_report_type = recipients_config.get('by_report_type', {})
            if by_report_type and report_type in by_report_type:
                raw_recipients = by_report_type.get(report_type, [])
            
            # Kiểm tra placeholder
            for email in raw_recipients:
                if 'example.com' in email.lower() or 'your-email' in email.lower():
                    print(f"\n⚠️  {report_type}: Phát hiện email placeholder - {email}")
                    print("   → Vui lòng sửa thành email thật trong email_config.yaml")
                    placeholder_found = True
            
            recipients = notifier._get_recipients(report_type)
            if recipients:
                has_recipients = True
                print(f"\n✅ {report_type} ({len(recipients)} ngườ i nhận):")
                for email in recipients:
                    print(f"   - {email}")
            else:
                print(f"\n⚠️  {report_type}: Chưa có ngườ i nhận hợp lệ")
        
        if placeholder_found:
            print("\n" + "=" * 60)
            print("⚠️  CẢNH BÁO: Vẫn còn email placeholder!")
            print("=" * 60)
            print("\n📋 Để sửa:")
            print("1. Mở file: ml_pipeline/email_config.yaml")
            print("2. Thay 'your-email@example.com' bằng email thật")
            print("3. Chạy lại: make ml-email-test")
        
        if not has_recipients:
            print("\n❌ Chưa có ngườ i nhận email hợp lệ nào!")
            print("\n📋 Hướng dẫn cấu hình:")
            print("1. Copy file template:")
            print("   cp ml_pipeline/email_config.example.yaml ml_pipeline/email_config.yaml")
            print("2. Sửa email_config.yaml, thay placeholder bằng email thật")
            print("3. Hoặc dùng biến môi trường:")
            print("   EMAIL_TRAINING_REPORT='your-email@company.com'")
            return False
        
        # Kiểm tra các loại thông báo
        print("\n" + "-" * 50)
        print("📧 Trạng thái thông báo:")
        notifications = config.get('notifications', {})
        for notif_type, settings in notifications.items():
            enabled = settings.get('enabled', False)
            status = "✅ Bật" if enabled else "❌ Tắt"
            prefix = settings.get('subject_prefix', 'N/A')
            print(f"   - {notif_type}: {status}")
            print(f"     Subject: {prefix}")
        
        # Kiểm tra SMTP config
        smtp_config = config.get('smtp', {})
        print(f"\n🔌 SMTP Configuration:")
        print(f"   - Server: {smtp_config.get('server', 'N/A')}")
        print(f"   - Port: {smtp_config.get('port', 'N/A')}")
        print(f"   - TLS: {'✅' if smtp_config.get('use_tls') else '❌'}")
        print(f"   - Sender: {smtp_config.get('sender_email', 'N/A')}")
        
        return has_recipients and not placeholder_found
        
    except Exception as e:
        print(f"❌ Lỗi khi đọc config: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_test_email():
    """Gửi email test"""
    print("\n" + "=" * 60)
    print("📤 GỬI EMAIL TEST")
    print("=" * 60)
    
    notifier = get_notifier()
    
    # Tạo nội dung test
    from datetime import datetime
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                      color: white; padding: 25px; border-radius: 10px 10px 0 0; text-align: center; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .success {{ color: #4caf50; font-size: 48px; text-align: center; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎉 Test Email Thành Công!</h1>
            </div>
            <div class="content">
                <div class="success">✅</div>
                <p style="text-align: center; font-size: 18px;">
                    Cấu hình email cho ML Pipeline đã hoạt động chính xác!
                </p>
                <p><strong>Thờ i gian test:</strong> {timestamp}</p>
                <p><strong>Sender:</strong> {notifier.config.get('smtp', {}).get('sender_email')}</p>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                <p style="color: #666; font-size: 14px; text-align: center;">
                    Bạn sẽ nhận được email tương tự khi:<br>
                    ✅ Training mô hình hoàn tất<br>
                    ✅ Dự báo được tạo ra<br>
                    ❌ Có lỗi xảy ra trong pipeline
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    subject = f"[ML Pipeline] Test Email - {timestamp}"
    
    # Gửi test cho tất cả các loại báo cáo có cấu hình
    report_types = ['training_report', 'forecast_report', 'error_alert']
    success_count = 0
    
    for report_type in report_types:
        recipients = notifier._get_recipients(report_type)
        if not recipients:
            continue
            
        print(f"\n⏳ Gửi test cho {report_type} ({len(recipients)} ngườ i nhận)...")
        test_subject = f"[Test {report_type}] {subject}"
        
        if notifier._send_email(test_subject, html_body, report_type=report_type):
            print(f"   ✅ {report_type}: Đã gửi thành công")
            success_count += 1
        else:
            print(f"   ❌ {report_type}: Gửi thất bại")
    
    success = success_count > 0
    
    if success:
        print("✅ Email test đã được gửi thành công!")
        print("\n📧 Vui lòng kiểm tra hộp thư đến (và thư rác) của bạn.")
        return True
    else:
        print("❌ Gửi email thất bại!")
        print("\n🔧 Các nguyên nhân phổ biến:")
        print("   1. EMAIL_PASSWORD không chính xác")
        print("   2. Tài khoản Gmail chưa bật 'Less secure app access' (nếu dùng password thường)")
        print("   3. Tường lửa chặn kết nối SMTP")
        print("   4. Email ngườ i nhận không hợp lệ")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Kiểm tra và test cấu hình email cho ML Pipeline'
    )
    parser.add_argument(
        '--send-test',
        action='store_true',
        help='Gửi email test sau khi kiểm tra'
    )
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='Đường dẫn đến file config YAML'
    )
    
    args = parser.parse_args()
    
    print("\n" + "🚀" * 30)
    print("ML PIPELINE - EMAIL NOTIFIER TEST")
    print("🚀" * 30 + "\n")
    
    # Kiểm tra environment
    env_ok = check_environment()
    
    # Kiểm tra config
    config_ok = check_config()
    
    if not env_ok or not config_ok:
        print("\n" + "=" * 60)
        print("❌ KIỂM TRA THẤT BẠI")
        print("=" * 60)
        print("\nVui lòng sửa lỗi ở trên trước khi tiếp tục.")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ KIỂM TRA THÀNH CÔNG")
    print("=" * 60)
    print("\nCấu hình email đã sẵn sàng!")
    
    if args.send_test:
        print()
        success = send_test_email()
        sys.exit(0 if success else 1)
    else:
        print("\n💡 Để gửi email test, chạy lệnh:")
        print("   python test_email.py --send-test")
        print("\n💡 Để train model và nhận email thông báo:")
        print("   python train_models.py")


if __name__ == '__main__':
    main()
