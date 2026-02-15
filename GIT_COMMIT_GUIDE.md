# Hướng Dẫn Commit Lên GitHub - Bảo Mật

> Hướng dẫn này giúp bạn commit code lên GitHub mà **KHÔNG** làm lộ thông tin cá nhân.

## ⚠️ DANH SÁCH FILE KHÔNG ĐƯỢC COMMIT

Các file sau chứa thông tin nhạy cảm và đã được thêm vào `.gitignore`:

- ❌ `.env` - Chứa password, API keys
- ❌ `ml_pipeline/email_config.yaml` - Chứa email cá nhân
- ❌ `*.pkl`, `*.joblib` - Model files (lớn + nhạy cảm)
- ❌ `csv_input/*.csv` - Dữ liệu thô
- ❌ `__pycache__/` - Cache Python

## 🚀 CÁCH COMMIT (TỪNG BƯỚC)

### Bước 1: Kiểm tra Git Status

```bash
cd /home/annduke/retail_data_pipeline

# Kiểm tra file nào đã thay đổi
git status
```

**Kết quả mong muốn:** Không thấy `.env` và `email_config.yaml` trong danh sách.

### Bước 2: Nếu chưa có Git Repository

```bash
# Khởi tạo repository
git init

# Thêm remote (thay YOUR_USERNAME bằng username GitHub của bạn)
git remote add origin https://github.com/YOUR_USERNAME/retail_data_pipeline.git
```

### Bước 3: Kiểm tra kỹ trước khi add

```bash
# Xem tất cả file sẽ được commit
git status

# Nếu thấy file nhạy cảm trong danh sách, KHÔNG ĐƯỢC add!
# Ví dụ: 
# ❌ .env
# ❌ ml_pipeline/email_config.yaml
```

### Bước 4: Add các file an toàn

**Cách 1: Add tất cả (Git sẽ tự động bỏ qua file trong .gitignore)**

```bash
git add .
```

**Cách 2: Add từng file cụ thể (an toàn hơn)**

```bash
# Core files
git add README.md
git add ARCHITECTURE.md
git add QUICK_REFERENCE.md
git add Makefile
git add docker-compose.yml
git add .gitignore

# ML Pipeline (KHÔNG add email_config.yaml)
git add ml_pipeline/email_config.example.yaml
git add ml_pipeline/email_notifier.py
git add ml_pipeline/test_email.py
git add ml_pipeline/xgboost_forecast.py
git add ml_pipeline/train_models.py
git add ml_pipeline/requirements.txt
git add ml_pipeline/Dockerfile
git add ml_pipeline/db_connectors.py
git add ml_pipeline/EMAIL_SETUP.md

# Config
git add config/

# Airflow
git add airflow/dags/

# DBT
git add dbt_retail/

# Init scripts
git add init/

# Data cleaning
git add data_cleaning/

# Superset
git add superset/
```

### Bước 5: Kiểm tra lại lần cuối

```bash
# Xem các file đã staged
git diff --cached --name-only

# Đảm bảo KHÔNG có:
# - .env
# - ml_pipeline/email_config.yaml
# - __pycache__/
# - *.pkl
```

### Bước 6: Commit

```bash
# Commit với message rõ ràng
git commit -m "feat: Add email notification system for ML pipeline

- Add email_notifier.py with HTML templates
- Support training_report, forecast_report, error_alert
- Add email_config.example.yaml as template
- Add security checks for placeholder emails
- Update .gitignore to protect sensitive configs

Security:
- email_config.yaml ignored (contains personal emails)
- .env ignored (contains passwords)
- Recipients can be set via environment variables"
```

### Bước 7: Push lên GitHub

```bash
# Nếu là lần đầu
git branch -M main
git push -u origin main

# Nếu đã có remote
git push origin main
```

## 🔍 KIỂM TRA SAU KHI COMMIT

### Kiểm tra trên GitHub

1. Mở repository trên GitHub
2. Vào tab "Commits"
3. Kiểm tra commit mới nhất
4. Đảm bảo KHÔNG thấy các file:
   - `.env`
   - `ml_pipeline/email_config.yaml`

### Kiểm tra bằng lệnh

```bash
# Xem lịch sử commit
git log --oneline -5

# Kiểm tra file trong commit
git ls-tree -r HEAD --name-only | grep -E "(\.env|email_config\.yaml)"
# Kết quả nên rỗng (không có gì)
```

## 🆘 XỬ LÝ SỰ CỐ

### Trường hợp 1: Đã vô tình add file nhạy cảm

```bash
# Xem file nào đang staged
git status

# Nếu thấy .env hoặc email_config.yaml trong "Changes to be committed":
git reset HEAD .env
git reset HEAD ml_pipeline/email_config.yaml

# Kiểm tra lại
git status
```

### Trường hợp 2: Đã commit nhầm file nhạy cảm (chưa push)

```bash
# Xóa file khỏi commit gần nhất nhưng giữ nguyên file trong working directory
git reset --soft HEAD~1

# Bỏ staged file nhạy cảm
git reset HEAD .env
git reset HEAD ml_pipeline/email_config.yaml

# Commit lại
git commit -m "Your commit message"
```

### Trường hợp 3: Đã push lên GitHub (NGHIÊM TRỌNG)

Nếu đã push file chứa password/email lên GitHub:

```bash
# 1. Xóa file khỏi Git history (file vẫn còn trong máy)
git filter-branch --force --index-filter \
"git rm --cached --ignore-unmatch .env ml_pipeline/email_config.yaml" \
--prune-empty --tag-name-filter cat -- --all

# 2. Force push (CẢNH BÁO: làm thay đổi history)
git push origin --force --all

# 3. Thay đổi password/email ngay lập tức!
# Vì đã bị lộ trên GitHub
```

## 📋 CHECKLIST TRƯỚC KHI PUSH

- [ ] `git status` không hiển thị `.env`
- [ ] `git status` không hiển thị `email_config.yaml`
- [ ] Không có file `.pkl`, `.joblib`
- [ ] Không có thư mục `__pycache__`
- [ ] Message commit rõ ràng
- [ ] Đã test chạy được trên local

## 🎯 VÍ DỤ HOÀN CHỈNH

```bash
# 1. Vào thư mục project
cd /home/annduke/retail_data_pipeline

# 2. Kiểm tra status
git status

# 3. Add files
git add .

# 4. Kiểm tra lại
git diff --cached --name-only | grep -E "(\.env|email_config\.yaml)"
# Nếu có kết quả → reset và bỏ qua file đó

# 5. Commit
git commit -m "feat: Add email notifications for ML pipeline

- Email notifier with HTML templates
- Support 3 report types: training, forecast, error
- Environment variable support for recipients
- Security: ignore sensitive config files"

# 6. Push
git push origin main

# 7. Kiểm tra trên GitHub
# Mở https://github.com/YOUR_USERNAME/retail_data_pipeline
```

## 📞 HỖ TRỢ

Nếu gặp lỗi:
1. Đừng panic - luôn có cách fix
2. Kiểm tra `git status`
3. Nếu đã push file nhạy cảm: đổi password ngay lập tức
