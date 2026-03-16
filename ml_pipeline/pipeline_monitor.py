#!/usr/bin/env python3
"""
Pipeline Monitor - Hiển thị log chi tiết cho toàn bộ pipeline
Sử dụng: python pipeline_monitor.py [stage]

Các stages:
  - spark: Log Spark ETL processing
  - sync: Log PostgreSQL → ClickHouse sync
  - dbt: Log DBT models build
  - ml: Log ML Training metrics và KPIs
  - forecast: Log Forecast results
  - all: Log tất cả các stages
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy import text
import logging

# Import database connectors từ db_connectors.py
from db_connectors import PostgreSQLConnector, ClickHouseConnector

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'  # Chỉ hiển thị message, không cần timestamp
)
logger = logging.getLogger(__name__)


class PipelineMonitor:
    """Monitor và hiển thị log chi tiết cho từng stage của pipeline"""
    
    # ANSI Color codes
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    
    def __init__(self):
        self.pg = PostgreSQLConnector()
        self.ch = ClickHouseConnector()
        
    def _print_banner(self, title: str, char: str = "═"):
        """In banner đẹp"""
        width = 70
        print(f"\n{self.BOLD}{self.BLUE}{char * width}{self.END}")
        print(f"{self.BOLD}{self.CYAN}  {title}{self.END}")
        print(f"{self.BOLD}{self.BLUE}{char * width}{self.END}\n")
        
    def _print_section(self, title: str):
        """In section header"""
        print(f"\n{self.BOLD}{self.YELLOW}▶ {title}{self.END}")
        print(f"{self.YELLOW}{'─' * 60}{self.END}")
        
    def _print_metric(self, label: str, value: Any, unit: str = "", color: str = None):
        """In một metric"""
        color_code = color or self.GREEN
        value_str = f"{value:,}" if isinstance(value, (int, float)) else str(value)
        print(f"  {label:<30} {color_code}{self.BOLD}{value_str:>15}{self.END} {unit}")
        
    def _print_kpi(self, label: str, value: Any, status: str = "good"):
        """In KPI với màu status"""
        colors = {
            "good": self.GREEN,
            "warning": self.YELLOW,
            "bad": self.RED,
            "info": self.CYAN
        }
        color = colors.get(status, self.GREEN)
        value_str = f"{value}" if not isinstance(value, float) else f"{value:.4f}"
        print(f"  {label:<35} {color}{self.BOLD}{value_str:>12}{self.END}")
    
    # ========================================================================
    # STAGE 1: SPARK ETL / CSV Processing
    # ========================================================================
    
    def log_spark_stage(self):
        """Log thông tin Spark ETL / CSV Processing"""
        self._print_banner("🔥 STAGE 1: SPARK ETL / CSV PROCESSING")
        
        try:
            # Kiểm tra các bảng chính
            tables_info = []
            
            with self.pg.get_connection() as conn:
                # Products
                try:
                    result = conn.execute(text("SELECT COUNT(*) FROM products"))
                    products_count = result.scalar()
                    tables_info.append(("Products", products_count))
                except:
                    products_count = 0
                    tables_info.append(("Products", 0))
                    
                # Transactions
                try:
                    result = conn.execute(text("SELECT COUNT(*) FROM transactions"))
                    transactions_count = result.scalar()
                    tables_info.append(("Transactions", transactions_count))
                except:
                    transactions_count = 0
                    tables_info.append(("Transactions", 0))
                    
                # Transaction Details
                try:
                    result = conn.execute(text("SELECT COUNT(*) FROM transaction_details"))
                    details_count = result.scalar()
                    tables_info.append(("Transaction Details", details_count))
                except:
                    details_count = 0
                    tables_info.append(("Transaction Details", 0))
                
                # Branches
                try:
                    result = conn.execute(text("SELECT COUNT(DISTINCT ma_chi_nhanh) FROM transactions"))
                    branches_count = result.scalar()
                except:
                    branches_count = 0
                
                # Date range
                try:
                    result = conn.execute(text("""
                        SELECT MIN(ngay_giao_dich), MAX(ngay_giao_dich) 
                        FROM transactions
                    """))
                    date_range = result.fetchone()
                    min_date, max_date = date_range if date_range else (None, None)
                except:
                    min_date, max_date = None, None
            
            # In thông tin
            self._print_section("📊 Dữ liệu đã xử lý trong PostgreSQL")
            for table_name, count in tables_info:
                self._print_metric(f"✓ {table_name}", count, "records")
                
            print(f"\n  {self.CYAN}Chi nhánh:{self.END} {branches_count}")
            if min_date and max_date:
                print(f"  {self.CYAN}Khoảng thờigian:{self.END} {min_date} → {max_date}")
                
            # Đánh giá
            total_records = sum([c for _, c in tables_info])
            if total_records > 0:
                print(f"\n{self.GREEN}✅ Spark ETL hoàn thành - Tổng {total_records:,} records{self.END}")
            else:
                print(f"\n{self.RED}⚠️ Chưa có dữ liệu - Cần chạy Spark ETL trước{self.END}")
                
        except Exception as e:
            logger.error(f"Lỗi khi log Spark stage: {e}")
            
    # ========================================================================
    # STAGE 2: Sync PostgreSQL → ClickHouse
    # ========================================================================
    
    def log_sync_stage(self):
        """Log thông tin đồng bộ PostgreSQL → ClickHouse"""
        self._print_banner("🔄 STAGE 2: SYNC POSTGRESQL → CLICKHOUSE")
        
        try:
            # PostgreSQL counts
            pg_counts = {}
            
            with self.pg.get_connection() as conn:
                for table in ['products', 'transactions', 'transaction_details', 'branches']:
                    try:
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        pg_counts[table] = result.scalar()
                    except:
                        pg_counts[table] = 0
            
            # ClickHouse counts
            ch_counts = {}
            try:
                for table in ['products', 'transactions', 'transaction_details', 'branches']:
                    try:
                        result = self.ch.client.execute(f"SELECT COUNT() FROM {table}")
                        ch_counts[table] = result[0][0] if result else 0
                    except:
                        ch_counts[table] = 0
            except Exception as e:
                logger.warning(f"Không thể đọc từ ClickHouse: {e}")
            
            # In bảng so sánh
            self._print_section("📊 So sánh dữ liệu PostgreSQL vs ClickHouse")
            print(f"\n  {'Table':<25} {'PostgreSQL':>12} {'ClickHouse':>12} {'Status':>10}")
            print(f"  {'─' * 65}")
            
            for table in ['products', 'transactions', 'transaction_details', 'branches']:
                pg_count = pg_counts.get(table, 0)
                ch_count = ch_counts.get(table, 0)
                
                if pg_count == ch_count and pg_count > 0:
                    status = f"{self.GREEN}✓ synced{self.END}"
                elif ch_count > 0:
                    status = f"{self.YELLOW}~ partial{self.END}"
                else:
                    status = f"{self.RED}✗ missing{self.END}"
                    
                print(f"  {table:<25} {pg_count:>12,} {ch_count:>12,} {status:>20}")
            
            # Tổng kết
            total_pg = sum(pg_counts.values())
            total_ch = sum(ch_counts.values())
            
            print(f"\n  {'─' * 65}")
            print(f"  {'TOTAL':<25} {total_pg:>12,} {total_ch:>12,}")
            
            if total_ch > 0:
                sync_pct = (total_ch / total_pg * 100) if total_pg > 0 else 0
                print(f"\n{self.GREEN}✅ Sync hoàn thành: {sync_pct:.1f}% dữ liệu đã đồng bộ{self.END}")
            else:
                print(f"\n{self.RED}⚠️ Chưa có dữ liệu trong ClickHouse - Cần chạy sync{self.END}")
                
        except Exception as e:
            logger.error(f"Lỗi khi log Sync stage: {e}")
            
    # ========================================================================
    # STAGE 3: DBT Build
    # ========================================================================
    
    def log_dbt_stage(self):
        """Log thông tin DBT Build"""
        self._print_banner("🏗️  STAGE 3: DBT BUILD")
        
        try:
            
            if not self.ch.client:
                print(f"{self.RED}❌ Không thể kết nối ClickHouse{self.END}")
                return
            
            # Kiểm tra các bảng marts chính
            marts_tables = [
                'fct_daily_sales',
                'fct_monthly_sales', 
                'fct_regular_sales',
                'fct_promotional_sales',
                'dim_product',
                'dim_branch',
                'dim_date'
            ]
            
            self._print_section("📊 DBT Marts Models")
            
            table_stats = []
            for table in marts_tables:
                try:
                    # Kiểm tra bảng tồn tại
                    result = self.ch.client.execute(f"SELECT COUNT() FROM {table}")
                    count = result[0][0] if result else 0
                    
                    # Lấy thêm thông tin về date range nếu có
                    date_info = ""
                    try:
                        if 'daily' in table or 'sales' in table:
                            date_result = self.ch.client.execute(f"""
                                SELECT MIN(transaction_date), MAX(transaction_date) 
                                FROM {table}
                            """)
                            if date_result and date_result[0]:
                                min_d, max_d = date_result[0]
                                date_info = f"({min_d} → {max_d})"
                    except:
                        pass
                    
                    table_stats.append((table, count, date_info))
                    
                except Exception as e:
                    table_stats.append((table, 0, "(not built)"))
            
            # In thông tin
            for table, count, date_info in table_stats:
                status = f"{self.GREEN}✓" if count > 0 else f"{self.RED}✗"
                print(f"  {status} {table:<30} {count:>10,} rows {self.CYAN}{date_info}{self.END}")
            
            # Kiểm tra data cho ML
            self._print_section("🤖 Data sẵn sàng cho ML Training")
            
            try:
                result = self.ch.client.execute("SELECT COUNT() FROM fct_regular_sales")
                ml_ready_count = result[0][0] if result else 0
                
                if ml_ready_count > 0:
                    print(f"\n  {self.GREEN}✅ fct_regular_sales: {ml_ready_count:,} records{self.END}")
                    print(f"  {self.GREEN}✅ Dữ liệu đã sẵn sàng cho ML Training{self.END}")
                    
                    # Thêm thông tin về products và branches trong fct_regular_sales
                    try:
                        prod_result = self.ch.client.execute("SELECT COUNT(DISTINCT product_code) FROM fct_regular_sales")
                        n_products = prod_result[0][0] if prod_result else 0
                        
                        branch_result = self.ch.client.execute("SELECT COUNT(DISTINCT branch_code) FROM fct_regular_sales")
                        n_branches = branch_result[0][0] if branch_result else 0
                        
                        print(f"\n  📦 Products: {n_products}")
                        print(f"  🏪 Branches: {n_branches}")
                    except:
                        pass
                else:
                    print(f"\n  {self.RED}⚠️ fct_regular_sales chưa có dữ liệu{self.END}")
                    print(f"  {self.YELLOW}💡 Cần chạy DBT build để tạo bảng cho ML{self.END}")
                    
            except Exception as e:
                print(f"  {self.RED}⚠️ Không thể kiểm tra fct_regular_sales: {e}{self.END}")
                
        except Exception as e:
            logger.error(f"Lỗi khi log DBT stage: {e}")
            
    # ========================================================================
    # STAGE 4: ML Training
    # ========================================================================
    
    def log_ml_stage(self):
        """Log thông tin ML Training"""
        self._print_banner("🤖 STAGE 4: ML TRAINING")
        
        try:
            # Đọc training metrics từ file
            metrics_path = '/app/models/training_metrics.json'
            
            if os.path.exists(metrics_path):
                with open(metrics_path, 'r') as f:
                    metrics = json.load(f)
                
                self._print_section("📈 Model Performance Metrics")
                
                # Hiển thị metrics cho từng model
                model_names = {
                    'daily_quantity': 'Model 1: Daily Quantity (MdAPE)',
                    'profit_margin': 'Model 2: Profit Margin (MAE)',
                    'category_daily_quantity': 'Model 3: Category Trend (MAPE)'
                }
                
                for model_key, model_metrics in metrics.items():
                    display_name = model_names.get(model_key, model_key)
                    tuning_method = model_metrics.get('tuning_method', 'default')
                    
                    print(f"\n  {self.BOLD}{self.CYAN}{display_name}{self.END}")
                    print(f"  Method: {self.YELLOW}{tuning_method.upper()}{self.END}")
                    
                    # Các metrics chính
                    primary_metric = model_metrics.get('primary_metric', 'N/A')
                    self._print_kpi("    Primary Metric", primary_metric)
                    
                    cv_score = model_metrics.get('cv_score', model_metrics.get('cv_mape', 'N/A'))
                    if isinstance(cv_score, float):
                        status = "good" if cv_score < 0.2 else ("warning" if cv_score < 0.5 else "bad")
                        self._print_kpi("    CV Score", cv_score, status)
                    
                    val_mape = model_metrics.get('val_mape', 'N/A')
                    if isinstance(val_mape, float):
                        status = "good" if val_mape < 20 else ("warning" if val_mape < 50 else "bad")
                        self._print_kpi("    Validation MAPE (%)", val_mape, status)
                    
                    val_mae = model_metrics.get('val_mae', 'N/A')
                    if isinstance(val_mae, float):
                        self._print_kpi("    Validation MAE", val_mae, "info")
                    
                    val_rmse = model_metrics.get('val_rmse', 'N/A')
                    if isinstance(val_rmse, float):
                        self._print_kpi("    Validation RMSE", val_rmse, "info")
                    
                    # Best params
                    best_params = model_metrics.get('best_params', {})
                    if best_params:
                        print(f"    {self.CYAN}Best Params:{self.END}")
                        for k, v in list(best_params.items())[:3]:
                            print(f"      • {k}: {v}")
                
                print(f"\n{self.GREEN}✅ Training hoàn thành - Metrics loaded từ training_metrics.json{self.END}")
            else:
                print(f"{self.YELLOW}⚠️ Không tìm thấy training_metrics.json{self.END}")
                print(f"{self.YELLOW}💡 Training có thể chưa chạy hoặc đang chạy{self.END}")
                
        except Exception as e:
            logger.error(f"Lỗi khi log ML stage: {e}")
            
    # ========================================================================
    # STAGE 5: Forecast
    # ========================================================================
    
    def log_forecast_stage(self):
        """Log thông tin Forecast"""
        self._print_banner("🔮 STAGE 5: FORECAST RESULTS")
        
        try:
            
            if not self.ch.client:
                print(f"{self.RED}❌ Không thể kết nối ClickHouse{self.END}")
                return
            
            # Kiểm tra bảng forecasts
            self._print_section("📊 Forecast Statistics")
            
            try:
                result = self.ch.client.execute("SELECT COUNT() FROM forecasts")
                forecast_count = result[0][0] if result else 0
                
                if forecast_count == 0:
                    print(f"{self.YELLOW}⚠️ Chưa có dữ liệu forecast{self.END}")
                    return
                
                print(f"\n  {self.GREEN}✅ Tổng số forecast records: {forecast_count:,}{self.END}")
                
                # Thống kê theo model
                try:
                    model_stats = self.ch.client.execute("""
                        SELECT model_name, COUNT(), 
                               AVG(predicted_quantity),
                               MAX(predicted_quantity)
                        FROM forecasts
                        GROUP BY model_name
                    """)
                    
                    print(f"\n  {self.BOLD}Theo Model:{self.END}")
                    for row in model_stats:
                        model_name, count, avg_qty, max_qty = row
                        print(f"    • {model_name:<30} {count:>6,} records")
                        print(f"      Avg Qty: {avg_qty:,.1f}, Max Qty: {max_qty:,.0f}")
                except Exception as e:
                    logger.warning(f"Không thể lấy stats theo model: {e}")
                
                # Date range của forecast
                try:
                    date_result = self.ch.client.execute("""
                        SELECT MIN(forecast_date), MAX(forecast_date),
                               COUNT(DISTINCT forecast_date)
                        FROM forecasts
                    """)
                    if date_result and date_result[0]:
                        min_date, max_date, n_days = date_result[0]
                        print(f"\n  {self.CYAN}Forecast Period:{self.END}")
                        print(f"    Từ: {min_date}")
                        print(f"    Đến: {max_date}")
                        print(f"    Số ngày: {n_days}")
                except:
                    pass
                
                # Top sản phẩm có forecast cao nhất
                try:
                    top_products = self.ch.client.execute("""
                        SELECT product_code, 
                               SUM(predicted_quantity) as total_qty,
                               AVG(confidence_score) as avg_conf
                        FROM forecasts
                        GROUP BY product_code
                        ORDER BY total_qty DESC
                        LIMIT 5
                    """)
                    
                    print(f"\n  {self.BOLD}Top 5 Products (by predicted quantity):{self.END}")
                    for i, (prod_code, total_qty, conf) in enumerate(top_products, 1):
                        conf_pct = conf * 100 if conf else 0
                        print(f"    {i}. {prod_code:<20} {total_qty:>10,.0f}  (conf: {conf_pct:.1f}%)")
                except Exception as e:
                    logger.warning(f"Không thể lấy top products: {e}")
                
                print(f"\n{self.GREEN}✅ Forecast đã sẵn sàng{self.END}")
                
            except Exception as e:
                print(f"{self.RED}❌ Lỗi khi đọc forecasts: {e}{self.END}")
                
        except Exception as e:
            logger.error(f"Lỗi khi log Forecast stage: {e}")
    
    # ========================================================================
    # LOG ALL STAGES
    # ========================================================================
    
    def log_all_stages(self):
        """Log tất cả các stages"""
        print(f"\n{self.BOLD}{self.BLUE}{'═' * 75}{self.END}")
        print(f"{self.BOLD}{self.CYAN}           PIPELINE MONITOR - FULL REPORT{self.END}")
        print(f"{self.BOLD}{self.BLUE}{'═' * 75}{self.END}")
        print(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{self.BOLD}{self.BLUE}{'═' * 75}{self.END}")
        
        self.log_spark_stage()
        self.log_sync_stage()
        self.log_dbt_stage()
        self.log_ml_stage()
        self.log_forecast_stage()
        
        # Summary
        self._print_banner("📋 PIPELINE SUMMARY")
        print(f"\n  {self.GREEN}✅ Monitor complete - Check each stage above for details{self.END}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Pipeline Monitor - Hiển thị log chi tiết cho ML Pipeline'
    )
    parser.add_argument(
        'stage',
        nargs='?',
        default='all',
        choices=['spark', 'sync', 'dbt', 'ml', 'forecast', 'all'],
        help='Stage cần monitor (default: all)'
    )
    
    args = parser.parse_args()
    
    monitor = PipelineMonitor()
    
    stage_methods = {
        'spark': monitor.log_spark_stage,
        'sync': monitor.log_sync_stage,
        'dbt': monitor.log_dbt_stage,
        'ml': monitor.log_ml_stage,
        'forecast': monitor.log_forecast_stage,
        'all': monitor.log_all_stages
    }
    
    method = stage_methods.get(args.stage)
    if method:
        method()
    else:
        print(f"Unknown stage: {args.stage}")


if __name__ == '__main__':
    main()
