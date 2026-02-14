# Hướng dẫn cấu hình Email Notifications cho ML Pipeline

> Tài liệu này hướng dẫn cách thiết lập thông báo email cho kết quả training và dự báo ML.

## ⚠️ QUAN TRỌNG - BẢO MẬT

File `email_config.yaml` chứa **email cá nhân** và đã được thêm vào `.gitignore`.  
**KHÔNG** commit file này lên GitHub!

```bash
# Kiểm tra file đã được ignore chưa
git check-ignore ml_pipeline/email_config.yaml
# Kết quả: ml_pipeline/email_config.yaml (OK)
```

## 🚀 Bắt đầu nhanh

### Bước 1: Tạo file cấu hình

```bash
cd ml_pipeline

# Copy từ template
cp email_config.example.yaml email_config.yaml

# Chỉnh sửa với email thật
nano email_config.yaml
```

### Bước 2: Cấu hình ngườ i nhận

Mở `email_config.yaml` và thay đổi các placeholder:

```yaml
recipients:
  by_report_type:
    training_report:
      - "data-scientist@yourcompany.com"  # ← Email thật
      
    forecast_report:
      - "sales-manager@yourcompany.com"   # ← Email thật
      
    error_alert:
      - "devops@yourcompany.com"          # ← Email thật
```

### Bước 3: Thiết lập Gmail App Password

1. **Bật 2-Factor Authentication** trong tài khoản Google
2. Truy cập: https://myaccount.google.com/apppasswords
3. Tạo App Password cho **"Mail"** > **"Other (Custom name)"**
4. Copy 16 ký tự App Password

### Bước 4: Thiết lập biến môi trường

Thêm vào file `.env`:

```bash
# Gmail SMTP
EMAIL_SENDER=your-email@gmail.com
EMAIL_PASSWORD=xxxx xxxx xxxx xxxx  # 16 ký tự App Password
```

### Bước 5: Kiểm tra và test

```bash
# Kiểm tra cấu hình
make ml-email-test

# Gửi email test
make ml-email-send-test
```

## 🔧 Cách 2: Dùng biến môi trường cho Recipients (Không cần file config)

Nếu không muốn dùng file `email_config.yaml`, bạn có thể định nghĩa recipients qua biến môi trường:

```bash
# Thêm vào .env
EMAIL_TRAINING_REPORT="data-scientist@company.com,ml-engineer@company.com"
EMAIL_FORECAST_REPORT="sales-manager@company.com,ceo@company.com"
EMAIL_ERROR_ALERT="devops@company.com"
```

Ưu tiên: Biến môi trường > File config

## 📧 Chi tiết từng loại báo cáo

### 1. Training Report (`training_report`)

**Gửi đến:** Data Scientist, ML Engineer, Tech Lead

**Nội dung:**
- CV MAPE, Validation MAPE, RMSE, MAE
- Best hyperparameters từ Optuna
- Feature importance
- File `training_metrics.json`

### 2. Forecast Report (`forecast_report`)

**Gửi đến:** Sales Manager, Inventory Team, Business Owner

**Nội dung:**
- Dự báo doanh số
- Top sản phẩm có nhu cầu cao
- Khuyến nghị tồn kho
- File `forecasts.csv`

### 3. Error Alert (`error_alert`)

**Gửi đến:** DevOps, IT Admin, Data Engineer

**Nội dung:**
- Chi tiết lỗi
- Stack trace
- Ngữ cảnh xảy ra lỗi

## ⚙️ Tùy chỉnh cấu hình

### Bật/tắt thông báo

```yaml
notifications:
  training_report:
    enabled: true        # true/false
    subject_prefix: "[ML Training] Kết quả huấn luyện"
```

### Thay đổi SMTP server

```yaml
smtp:
  server: "smtp.your-server.com"
  port: 587
  use_tls: true
```

## 🛠️ Sử dụng trong pipeline

```bash
# Training + gửi email
make ml-train

# Training + Predict + gửi email
make ml-train-predict

# Không gửi email
make ml-train-fast --no-email
```

## 🐛 Xử lý lỗi

| Lỗi | Nguyên nhân | Cách fix |
|-----|-------------|----------|
| "Chưa cấu hình EMAIL_PASSWORD" | Thiếu biến môi trường | Thêm vào `.env` |
| "Bỏ qua email placeholder" | Chưa sửa placeholder | Sửa `email_config.yaml` |
| "Không có ngườ i nhận" | Chưa cấu hình recipients | Thêm email vào config |

## 🔒 Checklist trước khi commit

- [ ] File `.env` đã được ignore
- [ ] File `email_config.yaml` đã được ignore
- [ ] Chỉ commit `email_config.example.yaml`
- [ ] Không có email cá nhân trong code Python
- [ ] Không có password trong bất kỳ file nào

## 📁 File structure

```
ml_pipeline/
├── email_config.yaml              # ⚠️ IGNORED - Chứa email thật
├── email_config.example.yaml      # ✅ COMMIT - Template
├── email_notifier.py              # ✅ COMMIT
├── test_email.py                  # ✅ COMMIT
├── xgboost_forecast.py            # ✅ COMMIT
└── EMAIL_SETUP.md                 # ✅ COMMIT
```

## 💡 Tips

1. **Dùng email công ty** thay vì Gmail cá nhân nếu có thể
2. **Test trước** với `make ml-email-send-test`
3. **Kiểm tra spam folder** nếu không nhận được email
4. **Giới hạn ngườ i nhận** mỗi loại không quá 10 ngườ i

## 📞 Hỗ trợ

Nếu gặp vấn đề:
1. Kiểm tra logs: `make logs`
2. Chạy test: `make ml-email-test`
3. Kiểm tra cấu hình: `cat ml_pipeline/email_config.yaml`
