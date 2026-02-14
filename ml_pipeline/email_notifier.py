"""
Email Notifier cho ML Pipeline
Gửi thông báo về kết quả training và dự báo qua Gmail
"""

import os
import re
import smtplib
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import json

import yaml
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmailNotifier:
    """
    Class gửi email thông báo cho ML Pipeline
    Hỗ trợ: training reports, forecast reports, error alerts
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Khởi tạo EmailNotifier
        
        Args:
            config_path: Đường dẫn đến file config YAML
        """
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), 
                'email_config.yaml'
            )
        
        self.config_path = config_path
        self.config = self._load_config()
        self.smtp_password = os.getenv('EMAIL_PASSWORD', '')
        
    def _load_config(self) -> Dict:
        """Load config từ YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"✅ Đã load email config từ {self.config_path}")
            return config
        except FileNotFoundError:
            logger.warning(f"⚠️ Không tìm thấy config file: {self.config_path}")
            return self._default_config()
        except Exception as e:
            logger.error(f"❌ Lỗi load config: {e}")
            return self._default_config()
    
    def _default_config(self) -> Dict:
        """Config mặc định khi không tìm thấy file"""
        return {
            'recipients': {'primary': '', 'additional': []},
            'notifications': {
                'training_report': {'enabled': True, 'subject_prefix': '[ML Pipeline] Training Report'},
                'forecast_report': {'enabled': True, 'subject_prefix': '[ML Pipeline] Forecast Report'},
                'error_alert': {'enabled': True, 'subject_prefix': '[ML Pipeline] ERROR Alert'}
            },
            'content': {
                'top_trending_products': 10,
                'top_inventory_alerts': 10,
                'date_format': '%d/%m/%Y %H:%M',
                'timezone': 'Asia/Ho_Chi_Minh'
            },
            'smtp': {
                'server': 'smtp.gmail.com',
                'port': 587,
                'use_tls': True,
                'sender_email': os.getenv('EMAIL_SENDER', 'ml-pipeline@company.com'),
                'sender_name': 'ML Pipeline System'
            },
            'advanced': {
                'timeout': 30,
                'retry_attempts': 3,
                'retry_delay': 5,
                'attach_metrics_file': True,
                'attach_forecasts_file': True
            }
        }
    
    def _get_recipients(self, report_type: Optional[str] = None) -> List[str]:
        """
        Lấy danh sách ngườ i nhận email theo loại báo cáo
        
        Thứ tự ưu tiên:
        1. Biến môi trường (EMAIL_TRAINING_REPORT, EMAIL_FORECAST_REPORT, EMAIL_ERROR_ALERT)
        2. File config (email_config.yaml)
        3. Fallback: cấu hình cũ (tương thích ngược)
        
        Args:
            report_type: Loại báo cáo ('training_report', 'forecast_report', 'error_alert')
                        Nếu None, trả về tất cả recipients
        
        Returns:
            List các email hợp lệ
        """
        recipients = []
        
        # 1. Ưu tiên 1: Đọc từ biến môi trường
        env_var_map = {
            'training_report': 'EMAIL_TRAINING_REPORT',
            'forecast_report': 'EMAIL_FORECAST_REPORT',
            'error_alert': 'EMAIL_ERROR_ALERT'
        }
        
        if report_type and report_type in env_var_map:
            env_emails = os.getenv(env_var_map[report_type], '')
            if env_emails:
                # Hỗ trợ nhiều email cách nhau bằng dấu phẩy
                recipients = [e.strip() for e in env_emails.split(',') if e.strip()]
                if recipients:
                    logger.info(f"📧 Đọc recipients từ biến môi trường {env_var_map[report_type]}")
        
        # 2. Nếu không có từ env, đọc từ file config
        if not recipients:
            recipients_config = self.config.get('recipients', {})
            
            # Cấu hình mới: phân quyền theo loại báo cáo
            by_report_type = recipients_config.get('by_report_type', {})
            
            if by_report_type and report_type:
                # Lấy danh sách ngườ i nhận theo loại báo cáo
                type_recipients = by_report_type.get(report_type, [])
                if type_recipients:
                    recipients.extend([email for email in type_recipients if email])
            
            # Fallback: cấu hình cũ (tương thích ngược)
            if not recipients:
                # Primary email
                primary = recipients_config.get('primary', '')
                if primary and primary != 'your-email@gmail.com':
                    recipients.append(primary)
                
                # Additional emails
                additional = recipients_config.get('additional', [])
                if additional:
                    recipients.extend([email for email in additional if email])
        
        # Lọc email placeholder và email không hợp lệ
        placeholder_patterns = ['example.com', 'your-email', 'company.com', '@test.', '@placeholder']
        filtered_emails = []
        for email in recipients:
            if self._is_valid_email(email):
                # Kiểm tra không phải placeholder
                if not any(pattern in email.lower() for pattern in placeholder_patterns):
                    filtered_emails.append(email)
                else:
                    logger.warning(f"⚠️ Bỏ qua email placeholder: {email}")
        
        # Loại bỏ trùng lặp
        valid_emails = list(set(filtered_emails))
        
        return valid_emails
    
    def _is_valid_email(self, email: str) -> bool:
        """Kiểm tra định dạng email hợp lệ"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def _send_email(self, subject: str, html_body: str, 
                    attachments: Optional[List[Tuple[str, str]]] = None,
                    report_type: Optional[str] = None) -> bool:
        """
        Gửi email với HTML content và attachments
        
        Args:
            subject: Tiêu đề email
            html_body: Nội dung HTML
            attachments: List các tuple (file_path, filename)
            report_type: Loại báo cáo để xác định ngườ i nhận
        
        Returns:
            True nếu gửi thành công
        """
        recipients = self._get_recipients(report_type)
        if not recipients:
            logger.warning("⚠️ Không có ngườ i nhận email nào được cấu hình")
            return False
        
        if not self.smtp_password:
            logger.warning("⚠️ Chưa cấu hình EMAIL_PASSWORD trong environment")
            return False
        
        smtp_config = self.config.get('smtp', {})
        sender_email = smtp_config.get('sender_email', 'ml-pipeline@company.com')
        sender_name = smtp_config.get('sender_name', 'ML Pipeline System')
        
        # Tạo message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{sender_name} <{sender_email}>"
        msg['To'] = ', '.join(recipients)
        
        # Thêm HTML content
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))
        
        # Thêm attachments
        if attachments:
            for file_path, filename in attachments:
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= "{filename}"'
                    )
                    msg.attach(part)
        
        # Gửi email với retry
        max_retries = self.config.get('advanced', {}).get('retry_attempts', 3)
        retry_delay = self.config.get('advanced', {}).get('retry_delay', 5)
        
        for attempt in range(max_retries):
            try:
                server = smtplib.SMTP(
                    smtp_config.get('server', 'smtp.gmail.com'),
                    smtp_config.get('port', 587),
                    timeout=self.config.get('advanced', {}).get('timeout', 30)
                )
                
                if smtp_config.get('use_tls', True):
                    server.starttls()
                
                server.login(sender_email, self.smtp_password)
                server.sendmail(sender_email, recipients, msg.as_string())
                server.quit()
                
                logger.info(f"✅ Email đã gửi thành công đến {len(recipients)} ngườ i nhận")
                return True
                
            except Exception as e:
                logger.error(f"❌ Lỗi gửi email (lần {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay)
        
        return False
    
    def send_training_report(self, metrics: Dict, training_duration: float = 0,
                           model_dir: str = '/app/models') -> bool:
        """
        Gửi báo cáo kết quả training cho recipients.training_report
        
        Args:
            metrics: Dict chứa metrics của các models
            training_duration: Thờ i gian training (giây)
            model_dir: Thư mục chứa models
        
        Returns:
            True nếu gửi thành công
        """
        if not self.config.get('notifications', {}).get('training_report', {}).get('enabled', True):
            logger.info("📧 Training report đã bị tắt trong config")
            return False
        
        # Kiểm tra có ngườ i nhận nào cho training_report không
        training_recipients = self._get_recipients('training_report')
        if not training_recipients:
            logger.warning("⚠️ Không có ngườ i nhận nào được cấu hình cho training_report")
            return False
        
        logger.info(f"📧 Chuẩn bị gửi training report đến {len(training_recipients)} ngườ i nhận: {training_recipients}")
        
        subject_prefix = self.config.get('notifications', {}).get('training_report', {}).get(
            'subject_prefix', '[ML Pipeline] Training Report'
        )
        
        timestamp = datetime.now().strftime(
            self.config.get('content', {}).get('date_format', '%d/%m/%Y %H:%M')
        )
        subject = f"{subject_prefix} - {timestamp}"
        
        # Tạo HTML body
        html_body = self._create_training_html(metrics, training_duration, timestamp)
        
        # Chuẩn bị attachments
        attachments = []
        if self.config.get('advanced', {}).get('attach_metrics_file', True):
            metrics_path = os.path.join(model_dir, 'training_metrics.json')
            if os.path.exists(metrics_path):
                attachments.append((metrics_path, 'training_metrics.json'))
        
        return self._send_email(subject, html_body, attachments, report_type='training_report')
    
    def _create_training_html(self, metrics: Dict, duration: float, timestamp: str) -> str:
        """Tạo HTML cho training report"""
        
        # Tạo rows cho metrics table
        metric_rows = ""
        for model_name, model_metrics in metrics.items():
            tuning_method = model_metrics.get('tuning_method', 'default')
            cv_mape = model_metrics.get('cv_mape', 'N/A')
            val_mape = model_metrics.get('val_mape', 'N/A')
            val_rmse = model_metrics.get('val_rmse', 'N/A')
            val_mae = model_metrics.get('val_mae', 'N/A')
            
            cv_mape_str = f"{cv_mape:.4f}" if isinstance(cv_mape, float) else str(cv_mape)
            val_mape_str = f"{val_mape:.4f}" if isinstance(val_mape, float) else 'N/A'
            val_rmse_str = f"{val_rmse:.2f}" if isinstance(val_rmse, float) else 'N/A'
            val_mae_str = f"{val_mae:.2f}" if isinstance(val_mae, float) else 'N/A'
            
            # Màu cho MAPE
            mape_color = self._get_mape_color(cv_mape if isinstance(cv_mape, float) else 1.0)
            
            metric_rows += f"""
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; font-weight: 500;">{model_name}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; text-align: center;">
                        <span style="background: {self._get_method_color(tuning_method)}; 
                                     color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px;">
                            {tuning_method.upper()}
                        </span>
                    </td>
                    <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; text-align: center; 
                               color: {mape_color}; font-weight: bold;">{cv_mape_str}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; text-align: center;">{val_mape_str}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; text-align: center;">{val_rmse_str}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; text-align: center;">{val_mae_str}</td>
                </tr>
            """
        
        # Tạo best params section
        params_section = ""
        for model_name, model_metrics in metrics.items():
            best_params = model_metrics.get('best_params', {})
            if best_params:
                params_html = "<br>".join([f"<code>{k}: {v}</code>" for k, v in list(best_params.items())[:5]])
                params_section += f"""
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 10px 0;">
                        <h4 style="margin: 0 0 10px 0; color: #333;">{model_name} - Best Parameters</h4>
                        <div style="font-size: 13px; color: #666;">{params_html}</div>
                    </div>
                """
        
        duration_min = duration / 60 if duration > 0 else 0
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                          color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .header p {{ margin: 10px 0 0 0; opacity: 0.9; }}
                .content {{ background: #ffffff; padding: 30px; border-radius: 0 0 10px 10px; 
                           box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                .summary {{ background: #e8f5e9; border-left: 4px solid #4caf50; 
                           padding: 15px; margin: 20px 0; border-radius: 4px; }}
                .summary h3 {{ margin: 0 0 10px 0; color: #2e7d32; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th {{ background: #f5f5f5; padding: 12px; text-align: left; 
                      font-weight: 600; color: #555; border-bottom: 2px solid #ddd; }}
                .footer {{ text-align: center; margin-top: 30px; padding-top: 20px; 
                          border-top: 1px solid #eee; color: #999; font-size: 12px; }}
                .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
                .badge-success {{ background: #4caf50; color: white; }}
                .badge-warning {{ background: #ff9800; color: white; }}
                .badge-error {{ background: #f44336; color: white; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🤖 ML Training Report</h1>
                    <p>Kết quả huấn luyện mô hình dự báo bán hàng</p>
                </div>
                
                <div class="content">
                    <div class="summary">
                        <h3>📊 Tổng quan</h3>
                        <p><strong>Thờ i gian training:</strong> {duration_min:.1f} phút</p>
                        <p><strong>Số models:</strong> {len(metrics)}</p>
                        <p><strong>Thờ i gian:</strong> {timestamp}</p>
                    </div>
                    
                    <h3 style="color: #333; border-bottom: 2px solid #667eea; padding-bottom: 10px;">
                        📈 Model Performance Metrics
                    </h3>
                    
                    <table>
                        <thead>
                            <tr>
                                <th>Model</th>
                                <th style="text-align: center;">Method</th>
                                <th style="text-align: center;">CV MAPE ↓</th>
                                <th style="text-align: center;">Val MAPE ↓</th>
                                <th style="text-align: center;">Val RMSE ↓</th>
                                <th style="text-align: center;">Val MAE ↓</th>
                            </tr>
                        </thead>
                        <tbody>
                            {metric_rows}
                        </tbody>
                    </table>
                    
                    <h3 style="color: #333; border-bottom: 2px solid #667eea; padding-bottom: 10px; margin-top: 30px;">
                        ⚙️ Hyperparameters
                    </h3>
                    {params_section if params_section else '<p style="color: #999;">Không có thông tin hyperparameters</p>'}
                    
                    <div style="background: #fff3e0; border-left: 4px solid #ff9800; 
                                padding: 15px; margin: 20px 0; border-radius: 4px;">
                        <h4 style="margin: 0 0 10px 0; color: #e65100;">📌 Giải thích Metrics</h4>
                        <ul style="margin: 0; padding-left: 20px; font-size: 13px; color: #666;">
                            <li><strong>MAPE (Mean Absolute Percentage Error):</strong> % sai số trung bình. &lt; 10% là rất tốt, 10-20% là tốt, &gt; 30% cần cải thiện.</li>
                            <li><strong>RMSE (Root Mean Square Error):</strong> Sai số trung bình, nhạy cảm với outliers.</li>
                            <li><strong>MAE (Mean Absolute Error):</strong> Sai số tuyệt đối trung bình.</li>
                        </ul>
                    </div>
                    
                    <div class="footer">
                        <p>🔄 Đây là email tự động từ ML Pipeline System</p>
                        <p>Retail Data Pipeline | Generated at {timestamp}</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    def send_forecast_report(self, forecasts: pd.DataFrame, 
                           inventory_recommendations: Optional[List[Dict]] = None,
                           model_dir: str = '/app/models') -> bool:
        """
        Gửi báo cáo kết quả dự báo cho recipients.forecast_report
        
        Args:
            forecasts: DataFrame chứa kết quả dự báo
            inventory_recommendations: List các khuyến nghị tồn kho
            model_dir: Thư mục chứa models
        
        Returns:
            True nếu gửi thành công
        """
        if not self.config.get('notifications', {}).get('forecast_report', {}).get('enabled', True):
            logger.info("📧 Forecast report đã bị tắt trong config")
            return False
        
        # Kiểm tra có ngườ i nhận nào cho forecast_report không
        forecast_recipients = self._get_recipients('forecast_report')
        if not forecast_recipients:
            logger.warning("⚠️ Không có ngườ i nhận nào được cấu hình cho forecast_report")
            return False
        
        logger.info(f"📧 Chuẩn bị gửi forecast report đến {len(forecast_recipients)} ngườ i nhận: {forecast_recipients}")
        
        subject_prefix = self.config.get('notifications', {}).get('forecast_report', {}).get(
            'subject_prefix', '[ML Pipeline] Forecast Report'
        )
        
        timestamp = datetime.now().strftime(
            self.config.get('content', {}).get('date_format', '%d/%m/%Y %H:%M')
        )
        subject = f"{subject_prefix} - {timestamp}"
        
        # Tạo HTML body
        html_body = self._create_forecast_html(forecasts, inventory_recommendations, timestamp)
        
        # Chuẩn bị attachments
        attachments = []
        if self.config.get('advanced', {}).get('attach_forecasts_file', True):
            # Lưu forecasts tạm thờ i để đính kèm
            temp_path = '/tmp/forecasts_latest.csv'
            forecasts.to_csv(temp_path, index=False)
            attachments.append((temp_path, 'forecasts_latest.csv'))
        
        return self._send_email(subject, html_body, attachments, report_type='forecast_report')
    
    def _create_forecast_html(self, forecasts: pd.DataFrame, 
                             inventory_recs: Optional[List[Dict]], timestamp: str) -> str:
        """Tạo HTML cho forecast report"""
        
        # Tính tổng hợp dự báo
        total_forecasted_qty = forecasts['predicted_quantity'].sum() if 'predicted_quantity' in forecasts.columns else 0
        total_forecasted_rev = forecasts['predicted_revenue'].sum() if 'predicted_revenue' in forecasts.columns else 0
        
        # Top sản phẩm có xu hướng tăng (predicted cao nhất)
        n_top = self.config.get('content', {}).get('top_trending_products', 10)
        if 'predicted_quantity' in forecasts.columns and 'ma_hang' in forecasts.columns:
            top_products = forecasts.groupby('ma_hang')['predicted_quantity'].sum().sort_values(ascending=False).head(n_top)
            top_products_html = ""
            for i, (product, qty) in enumerate(top_products.items(), 1):
                top_products_html += f"""
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #e0e0e0;">{i}</td>
                        <td style="padding: 10px; border-bottom: 1px solid #e0e0e0; font-weight: 500;">{product}</td>
                        <td style="padding: 10px; border-bottom: 1px solid #e0e0e0; text-align: right;">{int(qty):,}</td>
                    </tr>
                """
        else:
            top_products_html = '<tr><td colspan="3" style="text-align: center; color: #999;">Không có dữ liệu</td></tr>'
        
        # Khuyến nghị tồn kho
        inventory_html = ""
        if inventory_recs:
            n_alerts = self.config.get('content', {}).get('top_inventory_alerts', 10)
            for i, rec in enumerate(inventory_recs[:n_alerts], 1):
                urgency_color = '#f44336' if rec.get('reorder_urgency') == 'High' else '#ff9800'
                inventory_html += f"""
                    <div style="background: #fff8e1; border-left: 4px solid {urgency_color}; 
                                padding: 12px; margin: 8px 0; border-radius: 4px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-weight: 600; color: #333;">{rec.get('product_code', 'N/A')}</span>
                            <span style="background: {urgency_color}; color: white; padding: 2px 8px; 
                                        border-radius: 4px; font-size: 11px;">
                                {rec.get('reorder_urgency', 'Normal')}
                            </span>
                        </div>
                        <div style="font-size: 13px; color: #666; margin-top: 5px;">
                            Dự báo 7 ngày: <strong>{rec.get('predicted_next_7_days', 0):,.0f}</strong> | 
                            Safety Stock: <strong>{rec.get('recommended_safety_stock', 0):,}</strong> | 
                            Đề xuất đặt: <strong>{rec.get('suggested_order_quantity', 0):,}</strong>
                        </div>
                    </div>
                """
        else:
            inventory_html = '<p style="color: #999; text-align: center;">Không có khuyến nghị tồn kho đặc biệt</p>'
        
        # Date range
        if 'forecast_date' in forecasts.columns:
            min_date = pd.to_datetime(forecasts['forecast_date']).min().strftime('%d/%m/%Y')
            max_date = pd.to_datetime(forecasts['forecast_date']).max().strftime('%d/%m/%Y')
            date_range = f"{min_date} - {max_date}"
        else:
            date_range = "N/A"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); 
                          color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .content {{ background: #ffffff; padding: 30px; border-radius: 0 0 10px 10px; 
                           box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                .stats {{ display: flex; justify-content: space-around; margin: 20px 0; flex-wrap: wrap; }}
                .stat-box {{ text-align: center; padding: 20px; background: #f5f5f5; 
                            border-radius: 8px; min-width: 150px; margin: 5px; }}
                .stat-value {{ font-size: 24px; font-weight: bold; color: #11998e; }}
                .stat-label {{ font-size: 12px; color: #666; margin-top: 5px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th {{ background: #e8f5e9; padding: 12px; text-align: left; 
                      font-weight: 600; color: #2e7d32; border-bottom: 2px solid #4caf50; }}
                .footer {{ text-align: center; margin-top: 30px; padding-top: 20px; 
                          border-top: 1px solid #eee; color: #999; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔮 Forecast &amp; Inventory Report</h1>
                    <p>Báo cáo dự báo bán hàng và khuyến nghị tồn kho</p>
                </div>
                
                <div class="content">
                    <div class="stats">
                        <div class="stat-box">
                            <div class="stat-value">{len(forecasts):,}</div>
                            <div class="stat-label">Forecast Records</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value">{int(total_forecasted_qty):,}</div>
                            <div class="stat-label">Total Predicted Qty</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value">{total_forecasted_rev/1e6:.2f}M</div>
                            <div class="stat-label">Total Predicted Revenue</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value">{date_range}</div>
                            <div class="stat-label">Forecast Period</div>
                        </div>
                    </div>
                    
                    <h3 style="color: #333; border-bottom: 2px solid #11998e; padding-bottom: 10px;">
                        📈 Top {self.config.get('content', {}).get('top_trending_products', 10)} Sản phẩm có nhu cầu cao
                    </h3>
                    
                    <table>
                        <thead>
                            <tr>
                                <th style="width: 50px;">#</th>
                                <th>Mã sản phẩm</th>
                                <th style="text-align: right;">Số lượng dự báo</th>
                            </tr>
                        </thead>
                        <tbody>
                            {top_products_html}
                        </tbody>
                    </table>
                    
                    <h3 style="color: #333; border-bottom: 2px solid #11998e; padding-bottom: 10px; margin-top: 30px;">
                        📦 Khuyến nghị tồn kho
                    </h3>
                    
                    {inventory_html}
                    
                    <div style="background: #e3f2fd; border-left: 4px solid #2196f3; 
                                padding: 15px; margin: 20px 0; border-radius: 4px;">
                        <h4 style="margin: 0 0 10px 0; color: #1565c0;">💡 Hướng dẫn sử dụng</h4>
                        <ul style="margin: 0; padding-left: 20px; font-size: 13px; color: #555;">
                            <li><strong>Safety Stock:</strong> Mức tồn kho an toàn để tránh hết hàng (1.5x nhu cầu 7 ngày)</li>
                            <li><strong>Reorder Point:</strong> Ngưỡng cần đặt hàng lại (nhu cầu 2 tuần)</li>
                            <li><strong>High Urgency:</strong> Sản phẩm cần ưu tiên đặt hàng ngay</li>
                        </ul>
                    </div>
                    
                    <div class="footer">
                        <p>🔄 Đây là email tự động từ ML Pipeline System</p>
                        <p>Retail Data Pipeline | Generated at {timestamp}</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    def send_error_alert(self, error_message: str, context: str = "") -> bool:
        """
        Gửi thông báo lỗi cho recipients.error_alert
        
        Args:
            error_message: Nội dung lỗi
            context: Ngữ cảnh xảy ra lỗi
        
        Returns:
            True nếu gửi thành công
        """
        if not self.config.get('notifications', {}).get('error_alert', {}).get('enabled', True):
            logger.info("📧 Error alert đã bị tắt trong config")
            return False
        
        # Kiểm tra có ngườ i nhận nào cho error_alert không
        error_recipients = self._get_recipients('error_alert')
        if not error_recipients:
            logger.warning("⚠️ Không có ngườ i nhận nào được cấu hình cho error_alert")
            return False
        
        logger.info(f"📧 Chuẩn bị gửi error alert đến {len(error_recipients)} ngườ i nhận: {error_recipients}")
        
        subject_prefix = self.config.get('notifications', {}).get('error_alert', {}).get(
            'subject_prefix', '[ML Pipeline] ERROR Alert'
        )
        
        timestamp = datetime.now().strftime(
            self.config.get('content', {}).get('date_format', '%d/%m/%Y %H:%M')
        )
        subject = f"{subject_prefix} - {timestamp}"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #f44336; color: white; padding: 25px; 
                          border-radius: 10px 10px 0 0; text-align: center; }}
                .content {{ background: #ffffff; padding: 30px; 
                           border-radius: 0 0 10px 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                .error-box {{ background: #ffebee; border-left: 4px solid #f44336; 
                             padding: 15px; margin: 20px 0; border-radius: 4px; }}
                .error-box pre {{ margin: 0; font-family: monospace; font-size: 13px; color: #c62828; }}
                .footer {{ text-align: center; margin-top: 30px; color: #999; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>⚠️ ML Pipeline Error</h1>
                    <p>Đã xảy ra lỗi trong quá trình chạy pipeline</p>
                </div>
                
                <div class="content">
                    <p><strong>Thờ i gian:</strong> {timestamp}</p>
                    <p><strong>Context:</strong> {context or 'N/A'}</p>
                    
                    <div class="error-box">
                        <h4 style="margin: 0 0 10px 0; color: #c62828;">Error Message:</h4>
                        <pre>{error_message}</pre>
                    </div>
                    
                    <div class="footer">
                        <p>🔄 Email tự động từ ML Pipeline System</p>
                        <p>Vui lòng kiểm tra logs để biết thêm chi tiết</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self._send_email(subject, html, report_type='error_alert')
    
    def _get_mape_color(self, mape: float) -> str:
        """Trả về màu dựa trên giá trị MAPE"""
        if mape < 0.10:
            return '#4caf50'  # Xanh lá - rất tốt
        elif mape < 0.20:
            return '#8bc34a'  # Xanh lá nhạt - tốt
        elif mape < 0.30:
            return '#ff9800'  # Cam - trung bình
        else:
            return '#f44336'  # Đỏ - cần cải thiện
    
    def _get_method_color(self, method: str) -> str:
        """Trả về màu cho tuning method"""
        colors = {
            'optuna': '#9c27b0',      # Tím
            'random_search': '#2196f3',  # Xanh dương
            'default': '#757575'       # Xám
        }
        return colors.get(method, '#757575')


# Helper function để dễ sử dụng
def get_notifier(config_path: Optional[str] = None) -> EmailNotifier:
    """
    Factory function để tạo EmailNotifier instance
    
    Args:
        config_path: Đường dẫn đến config file
    
    Returns:
        EmailNotifier instance
    """
    return EmailNotifier(config_path)


if __name__ == '__main__':
    # Test email notifier
    notifier = get_notifier()
    
    # Test với sample data
    test_metrics = {
        'product_quantity': {
            'tuning_method': 'optuna',
            'cv_mape': 0.085,
            'val_mape': 0.092,
            'val_rmse': 15.5,
            'val_mae': 12.3,
            'best_params': {'max_depth': 6, 'learning_rate': 0.1}
        },
        'product_revenue': {
            'tuning_method': 'optuna',
            'cv_mape': 0.12,
            'val_mape': 0.115,
            'val_rmse': 250000,
            'val_mae': 180000,
            'best_params': {'max_depth': 8, 'learning_rate': 0.05}
        }
    }
    
    print("Testing email notifier...")
    print(f"Recipients: {notifier._get_recipients()}")
    print(f"Config loaded from: {notifier.config_path}")
