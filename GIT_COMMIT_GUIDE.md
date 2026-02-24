# Hướng Dẫn Push Dự Án Lên GitHub

> Hướng dẫn từng bước để push Retail Data Pipeline lên GitHub an toàn, không làm lộ thông tin nhạy cảm.

---

## 📋 Danh Sách File Được Bảo Vệ (Đã có trong .gitignore)

Các file sau **sẽ tự động bị ignore** khi commit:

| Loại | File/Thư mục | Lý do |
|------|-------------|-------|
| **Environment** | `.env`, `.env.local` | Chứa password, API keys |
| **Data** | `csv_input/*.csv`, `csv_output/` | Dữ liệu lớn, riêng tư |
| **ML Models** | `*.pkl`, `*.joblib`, `models/` | File lớn, tái tạo được |
| **Email Config** | `ml_pipeline/email_config.yaml` | Chứa email cá nhân |
| **Python Cache** | `__pycache__/`, `*.pyc` | Cache không cần thiết |
| **DBT** | `target/`, `dbt_packages/` | Build artifacts |
| **Airflow** | `logs/`, `*.pid` | Logs và temp files |
| **Docker** | `postgres_data/`, `*_data/` | Database volumes |

---

## 🚀 Các Bước Push Lên GitHub

### Bước 1: Kiểm tra Trạng Thái

```bash
cd /home/annduke/retail_data_pipeline

# Kiểm tra file nào đã thay đổi
git status

# Xem chi tiết thay đổi
git diff
```

**Lưu ý:** Đảm bảo không thấy file nhạy cảm như `.env` trong danh sách.

---

### Bước 2: Cấu hình Git (Nếu chưa có)

```bash
# Thiết lập username và email
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Kiểm tra remote URL
git remote -v

# Nếu chưa có remote, thêm mới:
git remote add origin https://github.com/annduke128/API_ETL_XGBoost.git
```

---

### Bước 3: Thêm File vào Staging

**Cách 1: Add tất cả (Git sẽ tự động bỏ qua file trong .gitignore)**

```bash
git add .
```

**Cách 2: Add từng phần (Kiểm soát tốt hơn)**

```bash
# Core project files
git add README.md ARCHITECTURE.md QUICK_REFERENCE.md AGENTS.md
git add Makefile docker-compose.yml .gitignore

# Source code
git add data_cleaning/
git add ml_pipeline/
git add dbt_retail/
git add airflow/dags/
git add superset/
git add init/
git add config/

# Scripts
git add process_csv.sh

# Documentation
git add GIT_COMMIT_GUIDE.md
```

---

### Bước 4: Kiểm Tra Lại Trước Khi Commit

```bash
# Xem danh sách file đã staged
git diff --cached --name-only

# Đảm bảo KHÔNG có các file sau:
# - .env
# - csv_input/*.csv
# - ml_pipeline/models/*.pkl
# - __pycache__/
# - ml_pipeline/email_config.yaml

# Nếu thấy file nhạy cảm, loại bỏ ngay:
git reset HEAD <tên-file>
```

---

### Bước 5: Commit

```bash
# Commit với message rõ ràng
git commit -m "feat: Major update - Remove MSSQL, add Optuna tuning

- Remove MSSQL service (reduce complexity)
- Add Optuna hyperparameter tuning for XGBoost
- Add Airflow DAG for daily CSV import (2AM schedule)
- Update documentation (README, AGENTS.md, ARCHITECTURE.md)
- Simplify CSV processing (remove real-time watcher)"
```

**Quy ước viết commit message:**
- `feat:` - Thêm tính năng mới
- `fix:` - Sửa lỗi
- `docs:` - Thay đổi documentation
- `refactor:` - Tái cấu trúc code
- `chore:` - Thay đổi nhỏ, maintenance

---

### Bước 6: Push Lên GitHub

#### Cách A: Dùng HTTPS + Personal Access Token (Khuyến nghị)

```bash
# 1. Tạo Personal Access Token trên GitHub:
#    Settings → Developer settings → Personal access tokens → Generate new token
#    Chọn quyền: repo

# 2. Cập nhật remote URL với token:
git remote set-url origin https://TOKEN@github.com/Annduke128/API_ETL_XGBoost.git

# 3. Push lên main branch:
git push -u origin main
```

#### Cách B: Dùng SSH Key

```bash
# 1. Tạo SSH key (nếu chưa có):
ssh-keygen -t ed25519 -C "your.email@example.com"

# 2. Copy public key:
cat ~/.ssh/id_ed25519.pub

# 3. Thêm vào GitHub:
#    Settings → SSH and GPG keys → New SSH key

# 4. Cập nhật remote URL:
git remote set-url origin git@github.com:Annduke128/API_ETL_XGBoost.git

# 5. Push:
git push -u origin main
```

#### Cách C: Dùng GitHub CLI

```bash
# Cài đặt gh CLI trước: https://cli.github.com/

# Đăng nhập
gh auth login

# Push
gh repo sync
```

---

## 🔍 Kiểm Tra Sau Khi Push

### 1. Kiểm tra trên GitHub

Mở: `https://github.com/Annduke128/API_ETL_XGBoost`

- [ ] Commit mới xuất hiện
- [ ] Không có file `.env`
- [ ] Không có file `*.pkl`
- [ ] Không có thư mục `__pycache__`
- [ ] Không có file CSV trong `csv_input/`

### 2. Kiểm tra bằng lệnh

```bash
# Xem commit mới nhất
git log --oneline -5

# Kiểm tra remote
git remote -v

# Kiểm tra branch
git branch -a
```

---

## 🆘 Xử Lý Lỗi Thường Gặp

### Lỗi 1: "fatal: could not read Username"

```bash
# Nguyên nhân: Chưa cấu hình xác thực
# Giải pháp: Dùng token hoặc SSH (xem Bước 6 bên trên)
```

### Lỗi 2: "rejected: non-fast-forward"

```bash
# Nguyên nhân: Có thay đổi trên remote chưa pull về
# Giải pháp:
git pull origin main --rebase
git push origin main
```

### Lỗi 3: Vô tình commit file nhạy cảm (chưa push)

```bash
# Loại bỏ file khỏi commit gần nhất
git reset --soft HEAD~1

# Bỏ file nhạy cảm khỏi staged
git reset HEAD .env

# Commit lại
git commit -m "Your commit message"
```

### Lỗi 4: Vô tình push file nhạy cảm lên GitHub

```bash
# 1. Xóa file khỏi Git history
git filter-branch --force --index-filter \
"git rm --cached --ignore-unmatch .env ml_pipeline/email_config.yaml" \
--prune-empty --tag-name-filter cat -- --all

# 2. Force push
git push origin --force --all

# 3. ĐỔI PASSWORD NGAY LẬP TỨC!
# Vì đã bị lộ trên GitHub
```

---

## ✅ Checklist Trước Khi Push

- [ ] Đã chạy `git status` kiểm tra
- [ ] Không có file `.env` trong staged
- [ ] Không có file `*.pkl`, `*.joblib`
- [ ] Không có thư mục `__pycache__`
- [ ] Không có file CSV trong `csv_input/`
- [ ] Commit message rõ ràng
- [ ] Đã test code chạy được trên local

---

## 📝 Ví Dụ Hoàn Chỉnh

```bash
# 1. Vào thư mục project
cd /home/annduke/retail_data_pipeline

# 2. Kiểm tra trạng thái
git status

# 3. Thêm tất cả file (trừ file trong .gitignore)
git add .

# 4. Kiểm tra lại
git diff --cached --name-only | grep -E "(\.env|\.pkl|csv_input)"
# Nếu có kết quả → reset và bỏ qua file đó

# 5. Commit
git commit -m "feat: Remove MSSQL, add Optuna tuning and Airflow scheduling

- Remove MSSQL to simplify architecture
- Add Optuna hyperparameter tuning
- Add Airflow DAG for daily CSV import at 2AM
- Update README and documentation"

# 6. Cấu hình remote với token (chỉ cần làm 1 lần)
git remote set-url origin https://YOUR_TOKEN@github.com/Annduke128/API_ETL_XGBoost.git

# 7. Push
git push -u origin main

# 8. Kiểm tra
git log --oneline -3
```

---

## 📚 Tham Khảo

- [GitHub Docs - Authentication](https://docs.github.com/en/authentication)
- [GitHub Docs - Managing remote repositories](https://docs.github.com/en/get-started/getting-started-with-git/managing-remote-repositories)
- [Git - Rewriting History](https://git-scm.com/book/en/v2/Git-Tools-Rewriting-History)

---

## 💡 Mẹo

1. **Luôn kiểm tra `git status` trước khi commit**
2. **Dùng `git diff --cached` để xem chính xác những gì sẽ được commit**
3. **Commit thường xuyên, push ít thường xuyên hơn**
4. **Viết commit message rõ ràng, mô tả được ý định thay đổi**

---

**Last Updated:** 2024-02-14
