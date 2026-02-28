# HASU Logo Assets

Thư mục này chứa logo cho email reports.

## Cách sử dụng

1. Copy file logo của bạn vào thư mục này:
   - Định dạng: PNG, JPG, JPEG
   - Kích thước khuyến nghị: 150x60px hoặc 300x120px
   - Tên file: `hasu_logo.png` (hoặc đổi trong .env)

2. Cập nhật `.env` nếu dùng tên file khác:
```bash
HASU_LOGO_PATH=/app/assets/hasu_logo.png
```

3. Khi chạy Docker/K8s, thư mục này sẽ được mount vào `/app/assets/` trong container.

## Docker Compose

Đã được mount trong `docker-compose.yml`:
```yaml
volumes:
  - ./ml_pipeline/assets:/app/assets:ro
```

## K8s

Thêm vào volumeMounts trong CronJob:
```yaml
volumeMounts:
  - name: logo-volume
    mountPath: /app/assets
volumes:
  - name: logo-volume
    configMap:
      name: hasu-logo
```

Hoặc copy logo vào Docker image trong Dockerfile.

## Lưu ý

- Nếu không có logo file, email sẽ hiển thị text "🏪 HASU" thay thế
- Logo sẽ được đính kèm inline trong email (CID attachment)
- Kích thước file nên < 100KB để email load nhanh
