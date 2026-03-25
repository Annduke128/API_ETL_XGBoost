"""
XGBoost Forecasting cho dự báo bán hàng và tồn kho
Sử dụng Optuna cho hyperparameter tuning
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Optional, Any
import logging
import joblib
import os
import json
import warnings

import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, mean_absolute_percentage_error

def median_absolute_percentage_error(y_true, y_pred):
    """MdAPE - Median Absolute Percentage Error, ít nhạy cảm với outliers hơn MAPE
    
    Filter out zeros để tránh division by zero.
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    mask = y_true > 0
    if mask.sum() == 0:
        return np.nan
    return np.median(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100

# Optuna cho Bayesian Optimization
try:
    import optuna
    from optuna.samplers import TPESampler
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    warnings.warn("Optuna not installed. Tuning will use RandomizedSearchCV instead.")

from db_connectors import PostgreSQLConnector, ClickHouseConnector
from email_notifier import EmailNotifier, get_notifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# GPU SUPPORT HELPER FUNCTIONS
# ============================================================================

def get_xgboost_tree_method() -> str:
    """
    Xác định tree_method dựa trên environment variable USE_GPU.
    
    Returns:
        str: 'gpu_hist' nếu USE_GPU=true và GPU available, 'hist' nếu không
    """
    use_gpu = os.environ.get('USE_GPU', 'false').lower() == 'true'
    
    if use_gpu:
        try:
            import subprocess
            result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info("🎮 GPU detected via nvidia-smi, using tree_method='gpu_hist'")
                return 'gpu_hist'
            else:
                logger.warning("⚠️  USE_GPU=true but nvidia-smi failed, falling back to CPU (hist)")
                return 'hist'
        except Exception as e:
            logger.warning(f"⚠️  USE_GPU=true but GPU check failed: {e}, falling back to CPU (hist)")
            return 'hist'
    
    return 'hist'


def get_xgboost_device() -> str:
    """
    Xác định device cho XGBoost.
    
    Returns:
        str: 'cuda' nếu GPU available, 'cpu' nếu không
    """
    tree_method = get_xgboost_tree_method()
    return 'cuda' if tree_method == 'gpu_hist' else 'cpu'


# Auto-detect GPU/CPU mode
TREE_METHOD = get_xgboost_tree_method()
DEVICE = get_xgboost_device()

if TREE_METHOD == 'gpu_hist':
    logger.info("🚀 XGBoost GPU mode enabled (gpu_hist)")
else:
    logger.info("🖥️  XGBoost CPU mode (hist)")


class SalesForecaster:
    """Dự báo doanh số bán hàng sử dụng XGBoost"""
    
    def __init__(self, model_dir: str = '/app/models', enable_email: bool = True):
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)
        
        self.pg = PostgreSQLConnector(
            host=os.getenv('POSTGRES_HOST'),
            database=os.getenv('POSTGRES_DB'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD')
        )
        
        self.ch = ClickHouseConnector(
            host=os.getenv('CLICKHOUSE_HOST', 'clickhouse'),
            database=os.getenv('CLICKHOUSE_DB', 'retail_dw'),
            user=os.getenv('CLICKHOUSE_USER', 'default'),
            password=os.getenv('CLICKHOUSE_PASSWORD', '')
        )
        
        self.models = {}
        self.metrics = {}
        self.studies = {}  # Lưu Optuna studies
        self.data_quality = {}  # Lưu thông tin chất lượng dữ liệu
        
        # Khởi tạo email notifier
        self.email_notifier = None
        if enable_email:
            try:
                self.email_notifier = get_notifier()
                logger.info("📧 Email notifier đã được khởi tạo")
            except Exception as e:
                logger.warning(f"⚠️ Không thể khởi tạo email notifier: {e}")
        self.feature_cols = []  # Sẽ được cập nhật động sau khi create_features
    
    def calculate_dynamic_percentiles(self, df: pd.DataFrame, columns: List[str] = ['daily_quantity'], 
                                      percentiles: List[float] = [0.95, 0.99]) -> Dict:
        """
        Tính toán percentiles động từ dữ liệu để xử lý outlier
        
        Args:
            df: DataFrame chứa dữ liệu
            columns: List các cột cần tính percentiles
            percentiles: List các mức percentile (mặc định [0.95, 0.99])
            
        Returns:
            Dict chứa percentiles cho mỗi cột
        """
        result = {}
        for col in columns:
            if col in df.columns:
                result[col] = {}
                for p in percentiles:
                    result[col][f'p{int(p*100)}'] = df[col].quantile(p)
                # Thêm thống kê bổ sung
                result[col]['mean'] = df[col].mean()
                result[col]['std'] = df[col].std()
                result[col]['max'] = df[col].max()
        return result
    
    def apply_winsorization(self, df: pd.DataFrame, column: str = 'daily_quantity', 
                           percentile: float = 0.99, inplace: bool = False) -> Tuple[pd.DataFrame, Dict]:
        """
        Áp dụng Winsorization (capping) để giảm ảnh hưởng của outliers
        
        Winsorization: Thay thế giá trị vượt ngưỡng P99 bằng chính giá trị P99
        
        Args:
            df: DataFrame chứa dữ liệu
            column: Tên cột cần winsorize (mặc định 'daily_quantity')
            percentile: Mức percentile để cap (mặc định 0.99 = P99)
            inplace: Nếu True, modify DataFrame gốc
            
        Returns:
            Tuple: (DataFrame đã winsorize, Dict thông tin winsorization)
        """
        if not inplace:
            df = df.copy()
        
        if column not in df.columns:
            logger.warning(f"⚠️ Cột {column} không tồn tại, bỏ qua winsorization")
            return df, {'applied': False}
        
        # Tính P99 động
        cap_value = df[column].quantile(percentile)
        original_max = df[column].max()
        original_mean = df[column].mean()
        
        # Đếm số outliers
        outliers_count = (df[column] > cap_value).sum()
        outliers_pct = outliers_count / len(df) * 100
        
        # Áp dụng winsorization (capping)
        df[column] = df[column].clip(upper=cap_value)
        
        # Thông tin winsorization
        stats = {
            'applied': True,
            'column': column,
            'percentile': percentile,
            'cap_value': float(cap_value),
            'original_max': float(original_max),
            'original_mean': float(original_mean),
            'new_mean': float(df[column].mean()),
            'outliers_count': int(outliers_count),
            'outliers_pct': float(outliers_pct),
            'total_records': len(df)
        }
        
        logger.info(f"✅ Winsorization applied to '{column}':")
        logger.info(f"   P{int(percentile*100)} = {cap_value:.2f}")
        logger.info(f"   Capped {outliers_count} outliers ({outliers_pct:.2f}%) from {original_max:.2f} → {cap_value:.2f}")
        logger.info(f"   Mean: {original_mean:.2f} → {df[column].mean():.2f}")
        
        return df, stats
    
    def load_historical_data(self, days: int = 0, apply_winsorize: bool = True) -> pd.DataFrame:
        """Load dữ liệu lịch sử từ ClickHouse (fct_regular_sales + JOIN seasonal factor)
        
        Cách 2B: Query từ fct_regular_sales (doanh số không khuyến mại) và JOIN với 
        int_dynamic_seasonal_factor để lấy seasonal factors.
        
        Args:
            days: Số ngày dữ liệu để load. Nếu 0, load toàn bộ dữ liệu.
            apply_winsorize: Nếu True, áp dụng winsorization cho daily_quantity
        """
        
        # Kiểm tra các bảng cần thiết
        check_query = """
        SELECT 
            sum(CASE WHEN name = 'fct_regular_sales' THEN 1 ELSE 0 END) as has_regular_sales,
            sum(CASE WHEN name = 'int_dynamic_seasonal_factor' THEN 1 ELSE 0 END) as has_seasonal
        FROM system.tables 
        WHERE database = 'retail_dw' AND name IN ('fct_regular_sales', 'int_dynamic_seasonal_factor')
        """
        try:
            check_result = self.ch.query(check_query)
            has_regular = check_result.iloc[0, 0] > 0
            has_seasonal = check_result.iloc[0, 1] > 0
        except:
            has_regular = False
            has_seasonal = False
        
        if not has_regular:
            logger.error("❌ Bảng fct_regular_sales chưa tồn tại. Cần chạy DBT models trước.")
            return pd.DataFrame()
        
        if not has_seasonal:
            logger.warning("⚠️ Bảng int_dynamic_seasonal_factor chưa tồn tại. Chạy fallback không có seasonal.")
            return self._load_from_regular_sales_no_seasonal(days)
        
        # Query từ fct_regular_sales + JOIN int_dynamic_seasonal_factor (Cách 2B)
        # Nếu days=0, load toàn bộ dữ liệu
        date_filter = f"AND f.transaction_date >= today() - {days}" if days > 0 else ""
        
        query = f"""
        SELECT
            f.transaction_date as ngay,
            f.branch_code as chi_nhanh,
            f.product_code as ma_hang,
            p.category_level_1 as nhom_hang_cap_1,
            p.category_level_2 as nhom_hang_cap_2,
            -- Time-based features tính từ ngay
            toDayOfWeek(f.transaction_date) as day_of_week,
            toDayOfMonth(f.transaction_date) as day_of_month,
            toMonth(f.transaction_date) as month,
            toWeek(f.transaction_date) as week_of_year,
            toDayOfWeek(f.transaction_date) IN (6, 7) as is_weekend,
            toDayOfMonth(f.transaction_date) = 1 as is_month_start,
            toDayOfMonth(f.transaction_date) = toDayOfMonth(toLastDayOfMonth(f.transaction_date)) as is_month_end,
            -- Holiday detection đơn giản
            multiIf(
                (toMonth(f.transaction_date) = 1 AND toDayOfMonth(f.transaction_date) <= 5), true,
                (toMonth(f.transaction_date) = 4 AND toDayOfMonth(f.transaction_date) = 30), true,
                (toMonth(f.transaction_date) = 5 AND toDayOfMonth(f.transaction_date) = 1), true,
                (toMonth(f.transaction_date) = 9 AND toDayOfMonth(f.transaction_date) = 2), true,
                false
            ) as is_holiday,
            -- DYNAMIC SEASONAL FACTORS (từ int_dynamic_seasonal_factor)
            COALESCE(s.is_peak_day, 0) as is_peak_day,
            COALESCE(s.peak_level, 0) as peak_level,
            COALESCE(s.seasonal_factor, 1.0) as seasonal_factor,
            COALESCE(s.revenue_factor, 1.0) as revenue_factor,
            COALESCE(s.quantity_factor, 1.0) as quantity_factor,
            s.peak_reason,
            -- Metrics (từ fct_regular_sales - không khuyến mại)
            f.gross_revenue as daily_revenue,
            f.quantity_sold as daily_quantity,
            f.gross_profit as daily_profit,
            f.transaction_count,
            -- Product metadata
            p.brand as thuong_hieu,
            p.abc_class
        FROM retail_dw.fct_regular_sales f
        LEFT JOIN retail_dw.dim_product p ON f.product_code = p.p.product_code
        LEFT JOIN (
            SELECT month,
                   argMax(seasonal_factor, calculated_at) as seasonal_factor,
                   argMax(revenue_factor, calculated_at) as revenue_factor,
                   argMax(quantity_factor, calculated_at) as quantity_factor,
                   argMax(is_peak_day, calculated_at) as is_peak_day,
                   argMax(peak_level, calculated_at) as peak_level,
                   argMax(peak_reason, calculated_at) as peak_reason
            FROM retail_dw.int_dynamic_seasonal_factor
            GROUP BY month
        ) s ON toMonth(f.transaction_date) = s.month
        WHERE f.product_code IS NOT NULL
          AND f.product_code != ''
          {date_filter}
        ORDER BY f.transaction_date
        """
        
        try:
            df = self.ch.query(query)
            df['ngay'] = pd.to_datetime(df['ngay'])
            # Fill NA cho category
            df['nhom_hang_cap_1'] = df['nhom_hang_cap_1'].fillna('Unknown')
            df['nhom_hang_cap_2'] = df['nhom_hang_cap_2'].fillna('Unknown')
            df['thuong_hieu'] = df['thuong_hieu'].fillna('Unknown')
            df['abc_class'] = df['abc_class'].fillna('C')
            
            # VALIDATION: Chỉ giữ lại records có dữ liệu bán thực tế
            original_count = len(df)
            
            # Loại bỏ records với quantity <= 0 hoặc NULL
            df = df[df['daily_quantity'].notna()]
            df = df[df['daily_quantity'] > 0]
            
            # Loại bỏ records với revenue <= 0 (double check)
            df = df[df['daily_revenue'].notna()]
            df = df[df['daily_revenue'] > 0]
            
            filtered_count = len(df)
            removed_count = original_count - filtered_count
            
            if removed_count > 0:
                logger.warning(f"⚠️  Đã loại bỏ {removed_count:,} records ({removed_count/original_count*100:.1f}%) do không có dữ liệu bán hàng (quantity=0 hoặc NULL)")
            
            if filtered_count == 0:
                logger.error("❌ Không có dữ liệu bán hàng hợp lệ sau khi lọc!")
                return pd.DataFrame()
            
            # Log thông tin về seasonal factors nếu có
            if 'seasonal_factor' in df.columns:
                avg_sf = df['seasonal_factor'].mean()
                peak_days = df['is_peak_day'].sum()
                logger.info(f"✅ Đã load {len(df):,} records bán hàng thực tế từ fct_regular_sales + dynamic seasonal")
                logger.info(f"   🎄 Avg seasonal factor: {avg_sf:.2f}, Peak days: {peak_days}")
            else:
                logger.info(f"✅ Đã load {len(df):,} records bán hàng thực tế từ fct_regular_sales (no seasonal)")
            
            # Thống kê chi tiết
            total_quantity = df['daily_quantity'].sum()
            total_revenue = df['daily_revenue'].sum()
            avg_quantity = df['daily_quantity'].mean()
            
            # Kiểm tra tính liên tục của dữ liệu theo thởigian
            date_range = pd.date_range(start=df['ngay'].min(), end=df['ngay'].max(), freq='D')
            actual_dates = df['ngay'].dt.date.unique()
            missing_dates = set(date_range.date) - set(actual_dates)
            
            logger.info(f"   📊 Date range: {df['ngay'].min()} to {df['ngay'].max()}")
            logger.info(f"   📊 Expected days: {len(date_range)}, Actual days with data: {len(actual_dates)}")
            
            if missing_dates:
                logger.warning(f"   ⚠️  Missing data for {len(missing_dates)} days: {sorted(list(missing_dates))[:5]}{'...' if len(missing_dates) > 5 else ''}")
            else:
                logger.info(f"   ✅ Complete daily data - no gaps detected")
            
            # Kiểm tra số ngày tối thiểu
            n_days = (df['ngay'].max() - df['ngay'].min()).days + 1
            if n_days < 14:
                logger.warning(f"   ⚠️  Only {n_days} days of data - recommend at least 14 days for accurate forecasting")
            elif n_days < 30:
                logger.info(f"   ⚠️  {n_days} days of data - acceptable for short-term forecasting")
            else:
                logger.info(f"   ✅ {n_days} days of data - good for forecasting")
            
            logger.info(f"   📊 Products: {df['ma_hang'].nunique()}, Branches: {df['chi_nhanh'].nunique()}")
            logger.info(f"   📊 Total quantity: {total_quantity:,.0f}, Total revenue: {total_revenue:,.0f}")
            logger.info(f"   📊 Avg daily quantity: {avg_quantity:.2f}")
            
            # Áp dụng Winsorization để giảm ảnh hưởng outliers
            if apply_winsorize and len(df) > 0:
                logger.info("🔧 Đang áp dụng Winsorization cho daily_quantity...")
                
                # Tính percentiles động
                percentiles = self.calculate_dynamic_percentiles(df, columns=['daily_quantity'])
                p99_value = percentiles.get('daily_quantity', {}).get('p99', df['daily_quantity'].quantile(0.99))
                
                logger.info(f"   📊 Dynamic P99 = {p99_value:.2f}")
                logger.info(f"   📊 Before winsorization: max={df['daily_quantity'].max():.2f}, mean={df['daily_quantity'].mean():.2f}")
                
                # Áp dụng winsorization
                df, win_stats = self.apply_winsorization(df, column='daily_quantity', percentile=0.99, inplace=True)
                
                # Lưu thông tin winsorization để sử dụng sau này
                self._winsorization_stats = win_stats
                
                logger.info(f"   ✅ After winsorization: max={df['daily_quantity'].max():.2f}, mean={df['daily_quantity'].mean():.2f}")
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Lỗi khi query fct_regular_sales: {e}")
            return self._load_from_daily_sales(days)
    
    def _load_from_regular_sales_no_seasonal(self, days: int = 0) -> pd.DataFrame:
        """Fallback: Load từ fct_regular_sales không có seasonal factors
        
        Args:
            days: Số ngày dữ liệu để load. Nếu 0, load toàn bộ dữ liệu.
        """
        date_filter = f"WHERE f.transaction_date >= today() - {days}" if days > 0 else ""
        
        query = f"""
        SELECT
            f.transaction_date as ngay,
            f.branch_code as chi_nhanh,
            f.product_code as ma_hang,
            p.category_level_1 as nhom_hang_cap_1,
            p.category_level_2 as nhom_hang_cap_2,
            toDayOfWeek(f.transaction_date) as day_of_week,
            toDayOfMonth(f.transaction_date) as day_of_month,
            toMonth(f.transaction_date) as month,
            toWeek(f.transaction_date) as week_of_year,
            toDayOfWeek(f.transaction_date) IN (6, 7) as is_weekend,
            toDayOfMonth(f.transaction_date) = 1 as is_month_start,
            toDayOfMonth(f.transaction_date) = toDayOfMonth(toLastDayOfMonth(f.transaction_date)) as is_month_end,
            multiIf(
                (toMonth(f.transaction_date) = 1 AND toDayOfMonth(f.transaction_date) <= 5), true,
                (toMonth(f.transaction_date) = 4 AND toDayOfMonth(f.transaction_date) = 30), true,
                (toMonth(f.transaction_date) = 5 AND toDayOfMonth(f.transaction_date) = 1), true,
                (toMonth(f.transaction_date) = 9 AND toDayOfMonth(f.transaction_date) = 2), true,
                false
            ) as is_holiday,
            f.gross_revenue as daily_revenue,
            f.quantity_sold as daily_quantity,
            f.gross_profit as daily_profit,
            f.transaction_count,
            p.brand as thuong_hieu,
            p.abc_class,
            -- Default seasonal factors (no seasonal table)
            0 as is_peak_day,
            1.0 as seasonal_factor,
            1.0 as revenue_factor,
            1.0 as quantity_factor,
            '' as peak_reason
        FROM retail_dw.fct_regular_sales f
        LEFT JOIN retail_dw.dim_product p ON f.product_code = p.p.product_code
        {date_filter}
        ORDER BY f.transaction_date
        """
        
        try:
            df = self.ch.query(query)
            df['ngay'] = pd.to_datetime(df['ngay'])
            df['nhom_hang_cap_1'] = df['nhom_hang_cap_1'].fillna('Unknown')
            df['nhom_hang_cap_2'] = df['nhom_hang_cap_2'].fillna('Unknown')
            df['thuong_hieu'] = df['thuong_hieu'].fillna('Unknown')
            df['abc_class'] = df['abc_class'].fillna('C')
            
            logger.info(f"✅ Đã load {len(df):,} records từ fct_regular_sales (no seasonal - fallback)")
            
            # Áp dụng Winsorization
            if apply_winsorize and len(df) > 0:
                logger.info("🔧 Đang áp dụng Winsorization cho daily_quantity (fallback)...")
                df, _ = self.apply_winsorization(df, column='daily_quantity', percentile=0.99, inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Lỗi khi query fct_regular_sales: {e}")
            return pd.DataFrame()
    
    def _load_from_daily_sales(self, days: int = 0) -> pd.DataFrame:
        """Fallback: Load từ fct_daily_sales nếu fct_regular_sales chưa có
        
        Args:
            days: Số ngày dữ liệu để load. Nếu 0, load toàn bộ dữ liệu.
        """
        
        check_query = """
        SELECT count() 
        FROM system.tables 
        WHERE database = 'retail_dw' AND name = 'fct_daily_sales'
        """
        try:
            table_exists = self.ch.query(check_query).iloc[0, 0] > 0
        except:
            table_exists = False
            
        if not table_exists:
            logger.error("❌ Không tìm thấy bảng fct_daily_sales")
            return pd.DataFrame(columns=[
                'ngay', 'chi_nhanh', 'ma_hang', 'nhom_hang_cap_1', 'nhom_hang_cap_2',
                'day_of_week', 'day_of_month', 'month', 'week_of_year', 'is_weekend',
                'is_month_start', 'is_month_end', 'is_holiday',
                'daily_revenue', 'daily_quantity', 'daily_profit', 'transaction_count'
            ])
        
        # Query từ fct_daily_sales, loại bỏ promotion products
        # Nếu days=0, load toàn bộ dữ liệu
        date_filter = f"AND f.transaction_date >= today() - {days}" if days > 0 else ""
        
        query = f"""
        SELECT
            f.transaction_date as ngay,
            f.branch_code as chi_nhanh,
            f.product_code as ma_hang,
            p.category_level_1 as nhom_hang_cap_1,
            p.category_level_2 as nhom_hang_cap_2,
            toDayOfWeek(f.transaction_date) as day_of_week,
            toDayOfMonth(f.transaction_date) as day_of_month,
            toMonth(f.transaction_date) as month,
            toWeek(f.transaction_date) as week_of_year,
            toDayOfWeek(f.transaction_date) IN (6, 7) as is_weekend,
            toDayOfMonth(f.transaction_date) = 1 as is_month_start,
            toDayOfMonth(f.transaction_date) = toDayOfMonth(toLastDayOfMonth(f.transaction_date)) as is_month_end,
            multiIf(
                (toMonth(f.transaction_date) = 1 AND toDayOfMonth(f.transaction_date) <= 5), true,
                (toMonth(f.transaction_date) = 4 AND toDayOfMonth(f.transaction_date) = 30), true,
                (toMonth(f.transaction_date) = 5 AND toDayOfMonth(f.transaction_date) = 1), true,
                (toMonth(f.transaction_date) = 9 AND toDayOfMonth(f.transaction_date) = 2), true,
                false
            ) as is_holiday,
            f.gross_revenue as daily_revenue,
            f.quantity_sold as daily_quantity,
            f.gross_profit as daily_profit,
            f.transaction_count,
            p.brand as thuong_hieu,
            p.abc_class
        FROM retail_dw.fct_daily_sales f
        LEFT JOIN retail_dw.dim_product p ON f.product_code = p.p.product_code
        WHERE lower(p.category_level_1) NOT LIKE '%khuyến mại%'
          AND lower(p.category_level_1) NOT LIKE '%khuyen mai%'
          {date_filter}
        ORDER BY f.transaction_date
        """
        
        try:
            df = self.ch.query(query)
            df['ngay'] = pd.to_datetime(df['ngay'])
            df['nhom_hang_cap_1'] = df['nhom_hang_cap_1'].fillna('Unknown')
            df['nhom_hang_cap_2'] = df['nhom_hang_cap_2'].fillna('Unknown')
            df['thuong_hieu'] = df['thuong_hieu'].fillna('Unknown')
            df['abc_class'] = df['abc_class'].fillna('C')
            
            logger.info(f"✅ Đã load {len(df):,} records từ fct_daily_sales (fallback, đã loại bỏ promotion)")
            
            # Áp dụng Winsorization
            if len(df) > 0:
                logger.info("🔧 Đang áp dụng Winsorization cho daily_quantity (fct_daily_sales fallback)...")
                df, _ = self.apply_winsorization(df, column='daily_quantity', percentile=0.99, inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Lỗi khi query fct_daily_sales: {e}")
            return pd.DataFrame(columns=[
                'ngay', 'chi_nhanh', 'ma_hang', 'nhom_hang_cap_1', 'nhom_hang_cap_2',
                'day_of_week', 'day_of_month', 'month', 'week_of_year', 'is_weekend',
                'is_month_start', 'is_month_end', 'is_holiday',
                'daily_revenue', 'daily_quantity', 'daily_profit', 'transaction_count'
            ])
    
            return pd.DataFrame(columns=[
                'ngay', 'chi_nhanh', 'ma_hang', 'nhom_hang_cap_1', 'nhom_hang_cap_2',
                'day_of_week', 'day_of_month', 'month', 'week_of_year', 'is_weekend',
                'is_month_start', 'is_month_end', 'is_holiday',
                'daily_revenue', 'daily_quantity', 'daily_profit', 'transaction_count',
                'is_peak_day', 'peak_level', 'seasonal_factor', 'revenue_factor', 'quantity_factor', 'peak_reason'
            ])
    
    def create_features(self, df: pd.DataFrame, prediction_mode: bool = False) -> pd.DataFrame:
        """
        Tạo features cho model.
        
        NOTE: Time-based features (day_of_week, month, is_weekend, etc.) 
        được tạo tự động từ cột 'ngay' để đảm bảo consistency giữa train và predict.
        Function này tạo:
        - Time-based features (từ ngay)
        - Dynamic seasonal factors (from ClickHouse/DBT)
        - Lag features
        - Rolling statistics  
        - Growth rate
        - Categorical encoding
        
        Args:
            df: DataFrame với dữ liệu
            prediction_mode: Nếu True, chỉ tạo lag features >= 7 ngày
                           để tránh sử dụng thông tin tuần hiện tại chưa dự báo
        """
        df = df.copy()
        
        # Đảm bảo ngay là datetime
        df['ngay'] = pd.to_datetime(df['ngay'])
        
        # Tạo time-based features từ ngay (quan trọng cho predict ngày tương lai)
        df['day_of_week'] = df['ngay'].dt.dayofweek + 1  # 1=Monday, 7=Sunday
        df['day_of_month'] = df['ngay'].dt.day
        df['month'] = df['ngay'].dt.month
        df['quarter'] = df['ngay'].dt.quarter  # EXTENDED: Quarter cho yearly seasonality
        df['day_of_year'] = df['ngay'].dt.dayofyear  # EXTENDED: Day of year
        df['week_of_year'] = df['ngay'].dt.isocalendar().week.astype(int)
        df['is_weekend'] = (df['day_of_week'] >= 6).astype(int)
        df['is_month_start'] = (df['day_of_month'] == 1).astype(int)
        df['is_month_end'] = (df['day_of_month'] == df['ngay'].dt.days_in_month).astype(int)
        
        # Holiday detection đơn giản (backup nếu không có từ ClickHouse)
        if 'is_holiday' not in df.columns:
            df['is_holiday'] = (
                ((df['month'] == 1) & (df['day_of_month'] <= 5)) |  # Tết
                ((df['month'] == 4) & (df['day_of_month'] == 30)) |  # 30/4
                ((df['month'] == 5) & (df['day_of_month'] == 1)) |   # 1/5
                ((df['month'] == 9) & (df['day_of_month'] == 2))     # 2/9
            ).astype(int)
        
        # Log thông tin về seasonal factors
        if 'seasonal_factor' in df.columns:
            avg_factor = df['seasonal_factor'].mean()
            peak_days = df['is_peak_day'].sum() if 'is_peak_day' in df.columns else 0
            logger.info(f"🎄 Using DYNAMIC seasonal factors (avg: {avg_factor:.2f}, peak days: {peak_days})")
        else:
            logger.warning("⚠️ No seasonal_factor found - using static seasonality only")
        
        # Lag features - điều chỉnh dựa trên số ngày dữ liệu có sẵn
        df = df.sort_values(['chi_nhanh', 'ma_hang', 'ngay'])
        n_unique_days = df['ngay'].nunique()
        
        # EXTENDED: Thêm lag 3 và 21 ngày cho model training sâu hơn
        all_lags = [1, 3, 7, 14, 21, 30]
        
        # Khi prediction_mode, chỉ dùng lag >= 7 để tránh dùng tuần hiện tại chưa dự báo
        if prediction_mode:
            all_lags = [lag for lag in all_lags if lag >= 7]
            if not all_lags:
                all_lags = [7]  # Mặc định tối thiểu lag 7 cho prediction
        
        available_lags = [lag for lag in all_lags if lag < n_unique_days]
        if not available_lags:
            available_lags = [min(7, n_unique_days - 1)] if n_unique_days > 1 else [1]
        
        if prediction_mode:
            logger.info(f"📊 Prediction mode - Lag features >= 7: {available_lags}")
        else:
            logger.info(f"📊 Training mode - Lag features: {available_lags} (dữ liệu có {n_unique_days} ngày)")
        
        for lag in available_lags:
            df[f'lag_{lag}_quantity'] = df.groupby(['chi_nhanh', 'ma_hang'])['daily_quantity'].shift(lag)
            df[f'lag_{lag}_revenue'] = df.groupby(['chi_nhanh', 'ma_hang'])['daily_revenue'].shift(lag)
        
        # Rolling statistics - giảm window nếu dữ liệu ít
        available_windows = [w for w in [7, 14, 30] if w <= n_unique_days]
        if not available_windows:
            available_windows = [min(3, n_unique_days)]  # Mặc định 3 ngày nếu ít dữ liệu
        
        for window in available_windows:
            df[f'rolling_mean_{window}_quantity'] = df.groupby(['chi_nhanh', 'ma_hang'])['daily_quantity'] \
                .transform(lambda x: x.rolling(window, min_periods=1).mean())
            df[f'rolling_std_{window}_quantity'] = df.groupby(['chi_nhanh', 'ma_hang'])['daily_quantity'] \
                .transform(lambda x: x.rolling(window, min_periods=1).std())
            # EXTENDED: Min/Max/Range cho volatility analysis
            df[f'rolling_min_{window}_quantity'] = df.groupby(['chi_nhanh', 'ma_hang'])['daily_quantity'] \
                .transform(lambda x: x.rolling(window, min_periods=1).min())
            df[f'rolling_max_{window}_quantity'] = df.groupby(['chi_nhanh', 'ma_hang'])['daily_quantity'] \
                .transform(lambda x: x.rolling(window, min_periods=1).max())
            df[f'rolling_range_{window}_quantity'] = df[f'rolling_max_{window}_quantity'] - df[f'rolling_min_{window}_quantity']
        
        # EXTENDED: Exponential Moving Average (EMA) - phản ứng nhanh hơn SMA
        for span in available_windows:
            df[f'ema_{span}_quantity'] = df.groupby(['chi_nhanh', 'ma_hang'])['daily_quantity'] \
                .transform(lambda x: x.ewm(span=span, adjust=False).mean())
        
        # EXTENDED: Price features
        df['avg_price'] = df['daily_revenue'] / (df['daily_quantity'] + 1e-8)
        df['price_change'] = df.groupby(['chi_nhanh', 'ma_hang'])['avg_price'].pct_change().fillna(0)
        df['price_change'] = df['price_change'].replace([np.inf, -np.inf], 0)
        
        # Growth rate - handle inf values
        df['quantity_growth'] = df.groupby(['chi_nhanh', 'ma_hang'])['daily_quantity'].pct_change()
        # Replace inf with NaN and fill with 0
        df['quantity_growth'] = df['quantity_growth'].replace([np.inf, -np.inf], np.nan).fillna(0)
        
        # Encoding cho categorical - đảm bảo kiểu int
        df['branch_encoded'] = pd.Categorical(df['chi_nhanh']).codes.astype(int)
        df['category1_encoded'] = pd.Categorical(df['nhom_hang_cap_1']).codes.astype(int)
        df['category2_encoded'] = pd.Categorical(df['nhom_hang_cap_2']).codes.astype(int)
        
        # Encode thêm brand và abc_class nếu có
        if 'thuong_hieu' in df.columns:
            df['brand_encoded'] = pd.Categorical(df['thuong_hieu'].fillna('Unknown')).codes.astype(int)
            df.drop(columns=['thuong_hieu'], inplace=True)  # Xoá cột gốc
        if 'abc_class' in df.columns:
            df['abc_encoded'] = pd.Categorical(df['abc_class'].fillna('C')).codes.astype(int)
            df.drop(columns=['abc_class'], inplace=True)  # Xoá cột gốc
        
        # Xoá peak_reason (string) nếu có - seasonal factor đã đủ thông tin
        if 'peak_reason' in df.columns:
            df.drop(columns=['peak_reason'], inplace=True)
        
        # Clean up any remaining inf or NaN in numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            df[col] = df[col].replace([np.inf, -np.inf], np.nan)
            df[col] = df[col].fillna(0)
        
        # Log các cột object còn lại (debug)
        object_cols = df.select_dtypes(include=['object']).columns.tolist()
        if object_cols:
            logger.info(f"   Object columns (sẽ bị loại khỏi features): {object_cols}")
        
        return df
    
    def train_model_optuna(self, df: pd.DataFrame, target_col: str = 'daily_quantity', 
                          n_trials: int = 50, timeout: int = 600, metric_type: str = 'mape') -> xgb.XGBRegressor:
        """
        Train XGBoost với Bayesian Optimization sử dụng Optuna
        
        Args:
            df: DataFrame với features
            target_col: Cột target cần dự báo
            n_trials: Số lần thử hyperparameters
            timeout: Thờigian tối đa (giây)
            metric_type: 'mape', 'mdape', hoặc 'mae' - metric để optimize
        
        Returns:
            XGBRegressor với best hyperparameters
        """
        if not OPTUNA_AVAILABLE:
            logger.warning("Optuna not available, falling back to RandomizedSearchCV")
            return self.train_model_random_search(df, target_col)
        
        # Chỉ dropna trong target, fillna cho features
        df_clean = df.dropna(subset=[target_col]).copy()
        
        # Kiểm tra dữ liệu sau khi dropna
        if len(df_clean) == 0:
            logger.error(f"❌ Không có dữ liệu sau khi loại bỏ NA cho target '{target_col}'")
            return xgb.XGBRegressor(
                objective='reg:squarederror',
                n_estimators=100,
                max_depth=3,
                random_state=42
            )
        
        # Tự động xác định feature columns
        exclude_cols = {'ngay', 'chi_nhanh', 'ma_hang', 'nhom_hang_cap_1', 'nhom_hang_cap_2', 
                       'daily_quantity', 'daily_revenue', 'daily_profit', 'transaction_count',
                       target_col}
        available_features = [col for col in df_clean.columns if col not in exclude_cols]
        
        if not available_features:
            logger.error(f"❌ Không có features nào phù hợp trong dữ liệu")
            return xgb.XGBRegressor(
                objective='reg:squarederror',
                n_estimators=100,
                max_depth=3,
                random_state=42
            )
        
        logger.info(f"📊 Optuna sử dụng {len(available_features)} features")
        
        # Lưu feature columns để dùng sau này
        self.feature_cols = available_features
        
        X = df_clean[available_features].fillna(0)
        y = df_clean[target_col]
        
        # Kiểm tra số lượng mẫu
        min_samples_required = 30  # Tối thiểu cho TimeSeriesSplit(n_splits=5)
        if len(X) < min_samples_required:
            logger.warning(f"⚠️ Ít dữ liệu ({len(X)} samples) cho target '{target_col}'. Sử dụng default params.")
            # Giảm n_trials cho dữ liệu nhỏ
            n_trials = min(n_trials, 10)
        
        # Time series split cho CV - giảm số folds nếu dữ liệu ít
        n_splits = min(5, len(X) // 6)  # Đảm bảo mỗi fold có ít nhất 6 samples
        if n_splits < 2:
            n_splits = 2
        tscv = TimeSeriesSplit(n_splits=n_splits)
        
        # Split train/val cho early stopping
        split_idx = int(len(X) * 0.8)
        if split_idx < 10:  # Đảm bảo train set có đủ dữ liệu
            split_idx = max(10, int(len(X) * 0.5))
        
        X_train_full, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train_full, y_val = y.iloc[:split_idx], y.iloc[split_idx:]
        
        # Kiểm tra lại train set
        if len(X_train_full) < n_splits * 2:
            logger.warning(f"⚠️ Không đủ dữ liệu cho CV. Giảm n_splits và tiếp tục tuning.")
            n_splits = max(2, len(X_train_full) // 3)
            tscv = TimeSeriesSplit(n_splits=n_splits)
        
        def objective(trial):
            """Objective function cho Optuna"""
            
            params = {
                'objective': 'reg:squarederror',
                'random_state': 42,
                'n_jobs': -1,  # Dùng tất cả 16 CPU cores
                'verbosity': 0,
                
                # CPU optimizations
                'tree_method': TREE_METHOD,  # Auto-detected: gpu_hist for GPU, hist for CPU
                'max_bin': 256,  # Giảm bins để tăng tốc
                
                # Tree structure - quan trọng nhất cho time series
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
                'gamma': trial.suggest_float('gamma', 0.0, 0.5, step=0.1),
                
                # Sampling - chống overfitting
                'subsample': trial.suggest_float('subsample', 0.6, 1.0, step=0.1),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0, step=0.1),
                'colsample_bylevel': trial.suggest_float('colsample_bylevel', 0.6, 1.0, step=0.1),
                
                # Regularization
                'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
                'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
                
                # Learning - số cây sẽ được điều chỉnh bởi early stopping
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'n_estimators': 2000,  # Cao, sẽ early stop
            }
            
            model = xgb.XGBRegressor(**params)
            
            # Cross-validation với TimeSeriesSplit
            cv_scores = []
            for train_idx, valid_idx in tscv.split(X_train_full):
                X_train_cv, X_valid_cv = X_train_full.iloc[train_idx], X_train_full.iloc[valid_idx]
                y_train_cv, y_valid_cv = y_train_full.iloc[train_idx], y_train_full.iloc[valid_idx]
                
                model.fit(
                    X_train_cv, y_train_cv,
                    eval_set=[(X_valid_cv, y_valid_cv)],
                    verbose=False
                )
                
                y_pred = model.predict(X_valid_cv)
                
                # Chọn metric phù hợp
                if metric_type == 'mdape':
                    # Median Absolute Percentage Error - ít nhạy với outliers
                    score = median_absolute_percentage_error(y_valid_cv, y_pred)
                elif metric_type == 'mae':
                    # Mean Absolute Error - phù hợp cho profit margin
                    score = mean_absolute_error(y_valid_cv, y_pred)
                else:  # mape
                    # Filter out zeros để tránh division by zero
                    mask = y_valid_cv > 0
                    if mask.sum() > 0:
                        score = mean_absolute_percentage_error(y_valid_cv[mask], y_pred[mask])
                    else:
                        score = np.nan
                
                cv_scores.append(score)
            
            return np.mean(cv_scores)
        
        # Tạo study với pruning
        study_name = f"{target_col}_study"
        study = optuna.create_study(
            direction='minimize',
            sampler=TPESampler(seed=42),
            pruner=optuna.pruners.MedianPruner(n_startup_trials=10, n_warmup_steps=20),
            study_name=study_name
        )
        
        logger.info(f"🔍 Starting Optuna tuning for '{target_col}' with {n_trials} trials...")
        study.optimize(objective, n_trials=n_trials, timeout=timeout, show_progress_bar=True)
        
        # Log kết quả
        metric_name = 'MdAPE' if metric_type == 'mdape' else ('MAE' if metric_type == 'mae' else 'MAPE')
        logger.info(f"✅ Best {metric_name}: {study.best_value:.4f}")
        logger.info(f"🎯 Best params: {study.best_params}")
        
        # Train final model với best params + early stopping
        best_params = study.best_params.copy()
        best_params.update({
            'objective': 'reg:squarederror',
            'random_state': 42,
            'n_jobs': -1,
            'n_estimators': 2000  # High, early stopping will find optimal
        })
        
        final_model = xgb.XGBRegressor(**best_params)
        final_model.fit(
            X_train_full, y_train_full,
            eval_set=[(X_val, y_val)],
            verbose=False
        )
        
        # Validation metrics - tính tất cả các metrics
        y_pred = final_model.predict(X_val)
        val_rmse = np.sqrt(mean_squared_error(y_val, y_pred))
        val_mae = mean_absolute_error(y_val, y_pred)
        val_mdape = median_absolute_percentage_error(y_val, y_pred)
        
        # MAPE có thể bị lỗi nếu y_val có giá trị 0, nên filter ra
        mask = y_val > 0
        if mask.sum() > 0:
            val_mape = mean_absolute_percentage_error(y_val[mask], y_pred[mask])
        else:
            val_mape = np.nan
        
        # Log theo metric type
        if metric_type == 'mdape':
            logger.info(f"📊 Validation MdAPE: {val_mdape:.4f}%")
            logger.info(f"📊 Validation MAPE:  {val_mape:.4f}% (reference)")
        elif metric_type == 'mape':
            logger.info(f"📊 Validation MAPE:  {val_mape:.4f}%")
            logger.info(f"📊 Validation MdAPE: {val_mdape:.4f}% (reference)")
        logger.info(f"📊 Validation RMSE:  {val_rmse:.4f}")
        logger.info(f"📊 Validation MAE:   {val_mae:.4f}")
        
        # Feature importance
        importance = pd.DataFrame({
            'feature': available_features,
            'importance': final_model.feature_importances_
        }).sort_values('importance', ascending=False)
        logger.info(f"🏆 Top 5 features:\n{importance.head().to_string()}")
        
        # Lưu metrics và study
        # Lấy best_iteration nếu có early stopping
        try:
            best_iter = final_model.best_iteration
        except:
            best_iter = final_model.n_estimators
            
        # Lưu metrics theo loại
        metrics_dict = {
            'tuning_method': 'optuna',
            'best_params': study.best_params,
            'val_rmse': val_rmse,
            'val_mae': val_mae,
            'val_mape': val_mape,
            'val_mdape': val_mdape,
            'best_iteration': best_iter,
            'n_trials': len(study.trials),
            'primary_metric': metric_type
        }
        
        # Lưu metric chính theo loại (để hiển thị trong summary)
        if metric_type == 'mdape':
            metrics_dict['cv_mdape'] = study.best_value
            metrics_dict['val_mdape'] = val_mdape
        elif metric_type == 'mae':
            metrics_dict['cv_mae'] = study.best_value
            metrics_dict['val_mae'] = val_mae
        else:
            metrics_dict['cv_mape'] = study.best_value
            metrics_dict['val_mape'] = val_mape
            
        self.metrics[target_col] = metrics_dict
        self.studies[target_col] = study
        
        # Lưu study
        study_path = os.path.join(self.model_dir, f'{target_col}_optuna_study.pkl')
        joblib.dump(study, study_path)
        logger.info(f"💾 Study saved to {study_path}")
        
        return final_model

    def train_model_random_search(self, df: pd.DataFrame, target_col: str = 'daily_quantity',
                                   n_iter: int = 20, metric_type: str = 'mape') -> xgb.XGBRegressor:
        """Fallback: RandomizedSearchCV khi Optuna không available
        
        Note: metric_type được truyền vào để tương thích API nhưng Random Search chỉ hỗ trợ MAPE
        """
        
        df_clean = df.dropna()
        X = df_clean[self.feature_cols]
        y = df_clean[target_col]
        
        tscv = TimeSeriesSplit(n_splits=5)
        
        param_distributions = {
            'max_depth': [3, 5, 6, 8, 10],
            'learning_rate': [0.01, 0.05, 0.1, 0.15, 0.2],
            'n_estimators': [200, 500, 800, 1000, 1500],
            'subsample': [0.6, 0.7, 0.8, 0.9, 1.0],
            'colsample_bytree': [0.6, 0.7, 0.8, 0.9, 1.0],
            'min_child_weight': [1, 3, 5, 7],
            'gamma': [0, 0.1, 0.2, 0.3],
            'reg_alpha': [0, 0.1, 1, 10],
            'reg_lambda': [0.1, 1, 5, 10]
        }
        
        base_model = xgb.XGBRegressor(
            objective='reg:squarederror',
            random_state=42,
            n_jobs=-1,
            tree_method=TREE_METHOD,
            max_bin=256
        )
        
        logger.info(f"🔍 Starting RandomizedSearchCV for '{target_col}'...")
        random_search = RandomizedSearchCV(
            estimator=base_model,
            param_distributions=param_distributions,
            n_iter=n_iter,
            scoring='neg_mean_absolute_percentage_error',
            cv=tscv,
            verbose=1,
            random_state=42,
            n_jobs=-1
        )
        
        random_search.fit(X, y)
        
        logger.info(f"✅ Best CV MAPE: {-random_search.best_score_:.4f}")
        logger.info(f"🎯 Best params: {random_search.best_params_}")
        
        self.metrics[target_col] = {
            'tuning_method': 'random_search',
            'best_params': random_search.best_params_,
            'cv_mape': -random_search.best_score_,
            'n_iter': n_iter
        }
        
        return random_search.best_estimator_
    
    def get_latest_data_date(self) -> Optional[date]:
        """Lấy ngày dữ liệu mới nhất trong ClickHouse - Trả về date object"""
        try:
            query = """
            SELECT max(transaction_date) as max_date
            FROM retail_dw.fct_regular_sales
            """
            result = self.ch.query(query)
            if result is not None and len(result) > 0 and result.iloc[0, 0] is not None:
                max_date = result.iloc[0, 0]
                if isinstance(max_date, str):
                    return pd.to_datetime(max_date).date()
                elif hasattr(max_date, 'date'):
                    return max_date.date()
                return max_date
            return None
        except Exception as e:
            logger.warning(f"⚠️ Không thể lấy ngày dữ liệu mới nhất: {e}")
            return None
    
    def get_last_training_date(self) -> Optional[date]:
        """Lấy ngày training gần nhất từ Redis hoặc file - Trả về date object"""
        try:
            date_str = None
            
            # Thử lấy từ Redis (nếu có)
            try:
                from redis_buffer import get_buffer
                redis = get_buffer()
                last_train = redis.client.get('ml_last_training_date')
                if last_train:
                    date_str = last_train.decode()
            except ImportError:
                pass
            
            # Nếu không có trong Redis, thử lấy từ file
            if date_str is None:
                timestamp_file = os.path.join(self.model_dir, '.last_training')
                if os.path.exists(timestamp_file):
                    with open(timestamp_file, 'r') as f:
                        date_str = f.read().strip()
            
            # Parse date string thành date object
            if date_str:
                # Hỗ trợ cả format cũ (datetime ISO) và format mới (date only)
                if 'T' in date_str or ' ' in date_str:
                    # Format cũ: 2026-02-21T10:30:00 hoặc 2026-02-21 10:30:00
                    return pd.to_datetime(date_str).date()
                else:
                    # Format mới: 2026-02-21
                    from datetime import datetime as dt
                    return dt.fromisoformat(date_str).date()
            
            return None
        except Exception as e:
            logger.debug(f"Không thể lấy ngày training gần nhất: {e}")
            return None
    
    def _load_models_if_exist(self) -> bool:
        """Load models từ file nếu tồn tại"""
        loaded = False
        for name in ['product_quantity', 'category_trend']:
            model_path = os.path.join(self.model_dir, f'{name}_model.pkl')
            if os.path.exists(model_path):
                try:
                    self.models[name] = joblib.load(model_path)
                    logger.info(f"✅ Loaded existing model: {name}")
                    loaded = True
                except Exception as e:
                    logger.warning(f"⚠️ Không thể load model {name}: {e}")
        return loaded
    
    def save_training_timestamp(self):
        """Lưu thờigian training hiện tại - Chỉ lưu date, không lưu time để tránh lỗi timezone"""
        try:
            # Chỉ lưu date (YYYY-MM-DD), không lưu time để tránh lỗi timezone
            now_date = datetime.now().date().isoformat()
            
            # Thử lưu vào Redis (nếu có)
            try:
                from redis_buffer import get_buffer
                redis = get_buffer()
                redis.client.set('ml_last_training_date', now_date)
            except ImportError:
                pass
            
            # Luôn lưu vào file
            timestamp_file = os.path.join(self.model_dir, '.last_training')
            with open(timestamp_file, 'w') as f:
                f.write(now_date)
                
        except Exception as e:
            logger.warning(f"⚠️ Không thể lưu timestamp training: {e}")
    
    def should_retrain(self, min_new_days: int = 1) -> tuple:
        """
        Kiểm tra có cần train lại không
        
        Returns:
            tuple: (should_train: bool, reason: str)
        """
        latest_date = self.get_latest_data_date()
        last_train_date = self.get_last_training_date()
        
        if latest_date is None:
            return False, "Không thể lấy ngày dữ liệu mới nhất"
        
        if last_train_date is None:
            return True, "Chưa có lịch sử training"
        
        # Cả hai đã là date objects sau khi refactor
        # Đảm bảo cùng kiểu date
        from datetime import date
        if not isinstance(latest_date, date):
            latest_date = pd.to_datetime(latest_date).date()
        if not isinstance(last_train_date, date):
            last_train_date = pd.to_datetime(last_train_date).date()
        
        days_diff = (latest_date - last_train_date).days
        
        if days_diff < min_new_days:
            return False, f"Không có dữ liệu mới (last_data={latest_date}, last_train={last_train_date}, diff={days_diff} days)"
        
        return True, f"Có dữ liệu mới: {days_diff} ngày kể từ lần train cuối"
    
    def train_all_models(self, n_trials: int = 50, days: int = 0, 
                         send_email: bool = True, tuning_method: str = 'optuna') -> Dict:
        """
        Train models cho tất cả levels (LUÔN dùng Optuna tuning)
        
        Args:
            n_trials: Số lần thử nghiệm hyperparameters (Optuna trials)
            days: Số ngày dữ liệu lịch sử để train
            send_email: Có gửi email thông báo không
            tuning_method: 'optuna' (mặc định) hoặc 'random_search' (fallback)
        
        Returns:
            Dict chứa metrics của tất cả models
        """
        import time
        start_time = time.time()
        
        logger.info("=" * 60)
        logger.info("🚀 BẮT ĐẦU TRAINING PIPELINE")
        logger.info("=" * 60)
        
        # Log thông tin dữ liệu (không dùng để quyết định skip)
        latest_data = self.get_latest_data_date()
        last_training = self.get_last_training_date()
        if latest_data and last_training:
            days_diff = (latest_data - last_training).days
            logger.info(f"📊 Latest data: {latest_data}, Last training: {last_training}, Diff: {days_diff} days")
        
        # Load data
        logger.info(f"📥 Loading {days} days of historical data...")
        df = self.load_historical_data(days=days)
        
        # VALIDATION: Kiểm tra dữ liệu sau khi load
        if df.empty:
            logger.error("❌ Không có dữ liệu để training!")
            return self.metrics
        
        logger.info(f"✅ Loaded {len(df):,} rows")
        logger.info(f"   📊 Total quantity: {df['daily_quantity'].sum():,.0f}")
        logger.info(f"   📊 Mean daily quantity: {df['daily_quantity'].mean():.2f}")
        logger.info(f"   📊 Unique products: {df['ma_hang'].nunique()}")
        logger.info(f"   📊 Date range: {df['ngay'].min()} to {df['ngay'].max()}")
        
        # VALIDATION: Kiểm tra đủ dữ liệu cho lag features
        n_unique_days = df['ngay'].nunique()
        date_range_days = (df['ngay'].max() - df['ngay'].min()).days + 1
        
        logger.info(f"   📊 Unique days in data: {n_unique_days}")
        logger.info(f"   📊 Calendar days in range: {date_range_days}")
        
        # Xác định lag features khả dụng
        available_lags = [lag for lag in [1, 7, 14, 30] if lag < n_unique_days]
        logger.info(f"   📊 Available lag features: {available_lags}")
        
        # Cảnh báo nếu thiếu dữ liệu cho lag quan trọng
        if n_unique_days < 31:
            logger.warning(f"   ⚠️  Chỉ có {n_unique_days} ngày dữ liệu - lag_30 sẽ không khả dụng")
        if n_unique_days < 15:
            logger.warning(f"   ⚠️  Chỉ có {n_unique_days} ngày dữ liệu - lag_14 sẽ không khả dụng")
        if n_unique_days < 8:
            logger.warning(f"   ⚠️  Chỉ có {n_unique_days} ngày dữ liệu - lag_7 sẽ không khả dụng")
        if n_unique_days < 2:
            logger.error(f"   ❌ Chỉ có {n_unique_days} ngày dữ liệu - Không đủ cho lag_1!")
            return self.metrics
        
        # Kiểm tra continuity của time-series (có ngày bị thiếu không)
        daily_counts = df.groupby('ngay').size()
        if len(daily_counts) < date_range_days * 0.8:  # Thiếu >20% ngày
            missing_days = date_range_days - len(daily_counts)
            logger.warning(f"   ⚠️  Thiếu {missing_days} ngày dữ liệu ({missing_days/date_range_days*100:.1f}%)")
        else:
            logger.info(f"   ✅ Time-series continuity: Good ({len(daily_counts)}/{date_range_days} days)")
        
        # Feature engineering
        logger.info("🔧 Creating features...")
        df_features = self.create_features(df)
        
        # VALIDATION: Kiểm tra sau feature engineering
        if df_features.empty:
            logger.error("❌ Không có dữ liệu sau khi tạo features!")
            return self.metrics
        
        # Kiểm tra target column
        if 'daily_quantity' not in df_features.columns:
            logger.error("❌ Không tìm thấy cột target 'daily_quantity'!")
            return self.metrics
        
        valid_targets = df_features['daily_quantity'].notna().sum()
        logger.info(f"✅ Created {len(self.feature_cols)} features")
        logger.info(f"   📊 Valid targets (non-NA): {valid_targets:,} / {len(df_features):,}")
        
        # VALIDATION: Kiểm tra lag features sau khi tạo
        lag_cols = [col for col in df_features.columns if col.startswith('lag_') and col.endswith('_quantity')]
        if lag_cols:
            logger.info(f"   📊 Lag features created: {lag_cols}")
            for lag_col in lag_cols:
                non_zero = (df_features[lag_col] != 0).sum()
                logger.info(f"      - {lag_col}: {non_zero:,} non-zero values ({non_zero/len(df_features)*100:.1f}%)")
        else:
            logger.warning(f"   ⚠️  No lag features found! Check data availability.")
        
        if valid_targets == 0:
            logger.error("❌ Không có target hợp lệ để training!")
            return self.metrics
        
        # Training function - LUÔN dùng Optuna tuning
        if OPTUNA_AVAILABLE:
            train_func = lambda df, target, metric_type='mape': self.train_model_optuna(df, target, n_trials=n_trials, metric_type=metric_type)
            logger.info(f"🎯 Using Optuna tuning with {n_trials} trials")
        else:
            train_func = lambda df, target, metric_type='mape': self.train_model_random_search(df, target, n_iter=n_trials, metric_type=metric_type)
            logger.info(f"🎯 Using Random Search with {n_trials} iterations (Optuna not available)")
        
        # Model 1: Product-level quantity forecast - Dùng MdAPE
        logger.info("\n" + "-" * 40)
        logger.info("📦 Model 1: Product-Level Quantity Forecast (MdAPE)")
        logger.info("-" * 40)
        self.models['product_quantity'] = train_func(df_features, 'daily_quantity', metric_type='mdape')
        
        # VALIDATION: Kiểm tra model đã train thành công
        if 'product_quantity' not in self.models or self.models['product_quantity'] is None:
            logger.error("❌ Model 1 training failed!")
        else:
            model = self.models['product_quantity']
            if hasattr(model, 'feature_importances_'):
                logger.info(f"✅ Model 1 trained successfully with {len(model.feature_importances_)} features")
            else:
                logger.warning("⚠️  Model 1 may not be trained properly (no feature_importances_)")
        
        # Model 2: Category Trend Forecast (Seasonal/Festival) - Độ tin cậy thấp nhất
        logger.info("\n" + "-" * 40)
        logger.info("📊 Model 2: Category Trend Forecast (Seasonal/Festival)")
        logger.info("   Mục tiêu: Xác định xu hướng bán hàng theo mùa/lễ tết")
        logger.info("   Độ tin cậy: LOW - Chỉ dùng cho xu hướng dài hạn")
        logger.info("-" * 40)
        
        # Aggregate lên category level (bao gồm cả seasonal factors)
        agg_dict = {
            'daily_quantity': 'sum',
            'daily_revenue': 'sum',
            'day_of_week': 'first',
            'day_of_month': 'first',
            'month': 'first',
            'week_of_year': 'first',
            'is_weekend': 'first',
            'is_month_start': 'first',
            'is_month_end': 'first',
            'is_holiday': 'first'
        }
        
        # Thêm seasonal factors nếu có
        if 'seasonal_factor' in df_features.columns:
            agg_dict['seasonal_factor'] = 'mean'  # Trung bình seasonal factor
            agg_dict['is_peak_day'] = 'max'  # Nếu có 1 ngày peak thì cả nhóm là peak
            agg_dict['revenue_factor'] = 'mean'
            agg_dict['quantity_factor'] = 'mean'
        
        category_df = df_features.groupby(['ngay', 'nhom_hang_cap_1']).agg(agg_dict).reset_index()
        
        category_df = category_df.sort_values(['nhom_hang_cap_1', 'ngay'])
        
        # Lag features cho category
        for lag in [1, 7, 14]:
            category_df[f'lag_{lag}_quantity'] = category_df.groupby('nhom_hang_cap_1')['daily_quantity'].shift(lag)
            category_df[f'lag_{lag}_revenue'] = category_df.groupby('nhom_hang_cap_1')['daily_revenue'].shift(lag)
        
        # Rolling statistics
        for window in [7, 14]:
            category_df[f'rolling_mean_{window}_quantity'] = category_df.groupby('nhom_hang_cap_1')['daily_quantity'] \
                .transform(lambda x: x.rolling(window, min_periods=1).mean())
        
        # Growth rate
        category_df['quantity_growth'] = category_df.groupby('nhom_hang_cap_1')['daily_quantity'].pct_change()
        category_df['quantity_growth'] = category_df['quantity_growth'].replace([np.inf, -np.inf], np.nan).fillna(0)
        
        # Encoding
        category_df['category1_encoded'] = pd.Categorical(category_df['nhom_hang_cap_1']).codes
        
        # Clean up
        numeric_cols = category_df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            category_df[col] = category_df[col].replace([np.inf, -np.inf], np.nan).fillna(0)
        
        # Dummy values cho category-level
        category_df['chi_nhanh'] = 'ALL_BRANCHES'
        category_df['ma_hang'] = 'ALL_PRODUCTS'
        category_df['nhom_hang_cap_2'] = 'ALL_CAT2'
        category_df['branch_encoded'] = 0
        category_df['category2_encoded'] = 0
        
        # Fill missing features
        for col in self.feature_cols:
            if col not in category_df.columns:
                category_df[col] = 0
        
        # Model 2 dùng target riêng để tránh ghi đè metrics
        category_df['category_daily_quantity'] = category_df['daily_quantity']
        # TODO: Model 2 cần metric riêng cho seasonal forecast (ví dụ: sMAPE)
        self.models['category_trend'] = train_func(category_df, 'category_daily_quantity', metric_type='mape')
        logger.info("⚠️  Lưu ý: Model 2 có độ tin cậy thấp - cần dữ liệu >= 1 năm để seasonal forecast chính xác")
        
        # Lưu models
        logger.info("\n" + "-" * 40)
        logger.info("💾 Saving models...")
        logger.info("-" * 40)
        for name, model in self.models.items():
            model_path = os.path.join(self.model_dir, f'{name}_model.pkl')
            joblib.dump(model, model_path)
            logger.info(f"✅ Saved: {name} → {model_path}")
        
        # Lưu metrics
        metrics_path = os.path.join(self.model_dir, 'training_metrics.json')
        with open(metrics_path, 'w', encoding='utf-8') as f:
            json.dump(self.metrics, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ Metrics saved to {metrics_path}")
        
        # Summary - Map model names to their target columns và metrics
        logger.info("\n" + "=" * 60)
        logger.info("📊 TRAINING SUMMARY")
        logger.info("=" * 60)
        
        # Map model names to (target_col, metric_label, cv_key, val_key)
        model_metric_map = {
            'product_quantity': ('daily_quantity', 'MdAPE', 'cv_mdape', 'val_mdape'),
            'category_trend': ('category_daily_quantity', 'MAPE', 'cv_mape', 'val_mape')
        }
        
        for model_name in self.models.keys():
            target_col, metric_label, cv_key, val_key = model_metric_map.get(
                model_name, (model_name, 'MAPE', 'cv_mape', 'val_mape')
            )
            
            # Lấy metrics từ self.metrics (key là target_col)
            metrics = self.metrics.get(target_col, {})
            cv_val = metrics.get(cv_key, 'N/A')
            val_val = metrics.get(val_key, 'N/A')
            
            logger.info(f"📈 {model_name}:")
            if isinstance(cv_val, (int, float)):
                logger.info(f"   CV {metric_label}: {cv_val:.4f}")
            else:
                logger.info(f"   CV {metric_label}: {cv_val}")
            if isinstance(val_val, (int, float)):
                logger.info(f"   Val {metric_label}: {val_val:.4f}")
        logger.info("=" * 60)
        
        # Lưu timestamp training
        self.save_training_timestamp()
        logger.info("💾 Đã lưu timestamp training")
        
        # Gửi email thông báo
        training_duration = time.time() - start_time
        if send_email and self.email_notifier:
            try:
                logger.info("📧 Đang gửi email thông báo training...")
                
                # Chuẩn bị data quality info
                data_quality_info = {
                    'cold_start_count': self.data_quality.get('cold_start_count', 0),
                    'fallback_used': self.data_quality.get('fallback_used', False),
                    'missing_data_pct': self.data_quality.get('missing_data_pct', 0),
                    'zero_predictions': self.data_quality.get('zero_predictions', 0),
                    'data_age_days': self.data_quality.get('data_age_days', 0),
                    'total_products': self.data_quality.get('total_products', 0)
                }
                
                success = self.email_notifier.send_training_report(
                    metrics=self.metrics,
                    training_duration=training_duration,
                    model_dir=self.model_dir,
                    data_quality=data_quality_info
                )
                if success:
                    logger.info("✅ Đã gửi email training report thành công")
                else:
                    logger.warning("⚠️ Không thể gửi email training report")
            except Exception as e:
                logger.error(f"❌ Lỗi khi gửi email: {e}")
        
        return self.metrics

    def get_tuning_summary(self, target_col: str = None) -> pd.DataFrame:
        """
        Trả về summary của Optuna study
        
        ⚠️ DEPRECATED: Chỉ dùng cho debug, không dùng trong workflow chính
        """
        warnings.warn(
            "get_tuning_summary() is deprecated and will be removed in future versions. "
            "Use training_metrics.json instead.",
            DeprecationWarning,
            stacklevel=2
        )
        if not OPTUNA_AVAILABLE or not self.studies:
            return pd.DataFrame()
        
        if target_col and target_col in self.studies:
            study = self.studies[target_col]
            trials_df = study.trials_dataframe()
            return trials_df
        
        # Tổng hợp tất cả studies
        summaries = []
        for name, study in self.studies.items():
            summaries.append({
                'model': name,
                'best_mape': study.best_value,
                'n_trials': len(study.trials),
                'best_params': str(study.best_params)
            })
        return pd.DataFrame(summaries)
    
    def get_top_abc_products(self, top_n: int = 50) -> pd.DataFrame:
        """
        Lấy Top N sản phẩm cần nhập từ dim_product (dựa trên doanh thu lịch sử).
        Loại bỏ các sản phẩm khuyến mại để đảm bảo dự báo baseline chính xác.
        ABC class chỉ dùng để phân loại, không giới hạn số lượng mỗi loại.
        Mặc định: 50 sản phẩm.
        """
        query = f"""
        SELECT 
            "p.product_code" as ma_hang,
            abc_class,
            total_historical_revenue
        FROM retail_dw.dim_product
        WHERE abc_class IN ('A', 'B', 'C')
          AND total_historical_revenue > 0
          AND lower(category_level_1) NOT LIKE '%khuyến mại%'
          AND lower(category_level_1) NOT LIKE '%khuyen mai%'
        ORDER BY total_historical_revenue DESC
        LIMIT {top_n}
        """
        
        df = self.ch.query(query)
        logger.info(f"📊 Đã chọn {len(df)} sản phẩm cần nhập (Top {top_n} theo doanh thu)")
        if len(df) > 0:
            abc_summary = df.groupby('abc_class').size().to_dict()
            for cls, count in abc_summary.items():
                logger.info(f"   - Loại {cls}: {count} sản phẩm")
        return df
    
    def predict_next_week(self, use_abc_filter: bool = True, abc_top_n: int = 50) -> pd.DataFrame:
        """
        Dự báo cho tuần tới với batch query và ABC-based product selection.
        Sử dụng Model 1 (product_quantity).
        
        Args:
            use_abc_filter: Nếu True, chỉ dự báo cho Top N sản phẩm cần nhập (mặc định: 50)
            abc_top_n: Số sản phẩm cần nhập để dự báo (mặc định: 50)
        
        Returns:
            DataFrame với dự báo cho 7 ngày tới
        """
        # Load models nếu chưa có
        if not self.models:
            for name in ['product_quantity', 'category_trend']:
                model_path = os.path.join(self.model_dir, f'{name}_model.pkl')
                if os.path.exists(model_path):
                    self.models[name] = joblib.load(model_path)
                    logger.info(f"✅ Loaded model: {name}")
        
        if 'product_quantity' not in self.models:
            raise ValueError("Model 'product_quantity' chưa được train hoặc load!")
        
        # Tạo future dates (7 ngày tới)
        future_dates = pd.date_range(
            start=datetime.now().date() + timedelta(days=1),
            periods=7,
            freq='D'
        )
        
        # BƯỚC 1: Chọn sản phẩm để dự báo
        if use_abc_filter:
            # Lấy Top N sản phẩm cần nhập
            abc_products = self.get_top_abc_products(top_n=abc_top_n)
            if len(abc_products) == 0:
                logger.warning("⚠️ Không tìm thấy sản phẩm ABC nào. Chuyển sang dự báo tất cả sản phẩm.")
                use_abc_filter = False
            else:
                product_list = abc_products['ma_hang'].tolist()
                product_abc_map = dict(zip(abc_products['ma_hang'], abc_products['abc_class']))
        
        if not use_abc_filter:
            # Lấy tất cả sản phẩm active từ fct_regular_sales (không khuyến mại)
            # Chỉ lấy sản phẩm có trong regular sales để đảm bảo dự báo baseline
            products_query = """
            SELECT DISTINCT product_code as ma_hang
            FROM retail_dw.fct_regular_sales
            WHERE transaction_date >= today() - 30
            """
            try:
                all_products = self.ch.query(products_query)
                product_list = all_products['ma_hang'].tolist()
                logger.info(f"✅ Loaded {len(product_list)} products from fct_regular_sales")
            except Exception as e:
                logger.warning(f"⚠️ Không thể query fct_regular_sales: {e}")
                logger.info("📌 Fallback: Sử dụng fct_daily_sales và loại bỏ promotion")
                products_query = """
                SELECT DISTINCT f.product_code as ma_hang
                FROM retail_dw.fct_daily_sales f
                LEFT JOIN retail_dw.dim_product p ON f.product_code = p.p.product_code
                WHERE f.transaction_date >= today() - 30
                  AND lower(p.category_level_1) NOT LIKE '%khuyến mại%'
                  AND lower(p.category_level_1) NOT LIKE '%khuyen mai%'
                """
                all_products = self.ch.query(products_query)
                product_list = all_products['ma_hang'].tolist()
            product_abc_map = {}
        
        logger.info(f"🔮 Dự báo cho {len(product_list)} sản phẩm x {len(future_dates)} ngày = {len(product_list) * len(future_dates)} dự báo")
        
        # BƯỚC 2a: Lấy DYNAMIC SEASONAL FACTORS cho ngày tương lai
        logger.info("📥 Đang tải dynamic seasonal factors cho ngày tương lai...")
        future_dates_str = "', '".join([d.strftime('%Y-%m-%d') for d in future_dates])
        
        # BƯỚC 2a: Kiểm tra và lấy DYNAMIC SEASONAL FACTORS cho ngày tương lai (Cách 2B)
        logger.info("📥 Đang tải dynamic seasonal factors cho ngày tương lai...")
        
        # Kiểm tra xem bảng int_dynamic_seasonal_factor có tồn tại không
        check_query = """
        SELECT count() 
        FROM system.tables 
        WHERE database = 'retail_dw' AND name = 'int_dynamic_seasonal_factor'
        """
        try:
            seasonal_table_exists = self.ch.query(check_query).iloc[0, 0] > 0
        except:
            seasonal_table_exists = False
        
        if seasonal_table_exists:
            # Query từ int_dynamic_seasonal_factor - lấy seasonal factors cho future months
            future_months = list(set([d.month for d in future_dates]))
            months_str = ', '.join([str(m) for m in future_months])
            
            seasonal_query = f"""
            SELECT 
                month,
                argMax(peak_reason, calculated_at) as peak_reason,
                argMax(seasonal_factor, calculated_at) as seasonal_factor,
                argMax(revenue_factor, calculated_at) as revenue_factor,
                argMax(quantity_factor, calculated_at) as quantity_factor,
                argMax(is_peak_day, calculated_at) as is_peak_day
            FROM retail_dw.int_dynamic_seasonal_factor
            WHERE month IN ({months_str})
            GROUP BY month
            """
            try:
                seasonal_df = self.ch.query(seasonal_query)
                # Tạo mapping từ month -> seasonal factors
                seasonal_map = {}
                for _, row in seasonal_df.iterrows():
                    month = int(row['month'])
                    seasonal_map[month] = {
                        'peak_reason': row.get('peak_reason', ''),
                        'seasonal_factor': float(row.get('seasonal_factor', 1.0)),
                        'revenue_factor': float(row.get('revenue_factor', 1.0)),
                        'quantity_factor': float(row.get('quantity_factor', 1.0)),
                        'is_peak_day': int(row.get('is_peak_day', 0))
                    }
                logger.info(f"✅ Loaded dynamic seasonal factors: {len(seasonal_map)} months")
                for m, data in seasonal_map.items():
                    logger.info(f"   📅 Month {m}: {data['peak_reason'] or 'Normal'} (factor: {data['seasonal_factor']})")
            except Exception as e:
                logger.warning(f"⚠️ Could not load dynamic seasonal factors: {e}")
                seasonal_map = {}
        else:
            logger.warning("⚠️ Bảng int_dynamic_seasonal_factor chưa tồn tại")
            seasonal_map = {}
        
        # BƯỚC 2b: Batch query - Lấy toàn bộ dữ liệu lịch sử từ fct_regular_sales (Cách 2B)
        logger.info("📥 Đang tải dữ liệu lịch sử từ fct_regular_sales + JOIN seasonal...")
        
        # Tạo chuỗi product codes cho SQL IN clause
        product_codes_str = "', '".join(str(p) for p in product_list)
        
        # Sử dụng Cách 2B: fct_regular_sales + LEFT JOIN int_dynamic_seasonal_factor
        if seasonal_table_exists:
            history_query = f"""
            SELECT 
                f.transaction_date as ngay,
                f.branch_code as chi_nhanh,
                f.product_code as ma_hang,
                p.product_name as ten_san_pham,
                p.category_level_1 as nhom_hang_cap_1,
                p.category_level_2 as nhom_hang_cap_2,
                -- Doanh số từ fct_regular_sales (không khuyến mại)
                f.gross_revenue as daily_revenue,
                f.quantity_sold as daily_quantity,
                f.gross_profit as daily_profit,
                f.transaction_count,
                p.brand as thuong_hieu,
                p.abc_class,
                -- DYNAMIC SEASONAL FACTORS (từ int_dynamic_seasonal_factor)
                COALESCE(s.is_peak_day, 0) as is_peak_day,
                COALESCE(s.peak_level, 0) as peak_level,
                COALESCE(s.seasonal_factor, 1.0) as seasonal_factor,
                COALESCE(s.revenue_factor, 1.0) as revenue_factor,
                COALESCE(s.quantity_factor, 1.0) as quantity_factor,
                s.peak_reason
            FROM retail_dw.fct_regular_sales f
            LEFT JOIN retail_dw.dim_product p ON f.product_code = p.p.product_code
            LEFT JOIN (
                SELECT month,
                       argMax(seasonal_factor, calculated_at) as seasonal_factor,
                       argMax(revenue_factor, calculated_at) as revenue_factor,
                       argMax(quantity_factor, calculated_at) as quantity_factor,
                       argMax(is_peak_day, calculated_at) as is_peak_day,
                       argMax(peak_level, calculated_at) as peak_level,
                       argMax(peak_reason, calculated_at) as peak_reason
                FROM retail_dw.int_dynamic_seasonal_factor
                GROUP BY month
            ) s ON toMonth(f.transaction_date) = s.month
            WHERE f.product_code IN ('{product_codes_str}')
              AND f.transaction_date >= today() - 60
            ORDER BY f.branch_code, f.product_code, f.transaction_date
            """
        else:
            # Fallback nếu bảng mới chưa tồn tại
            history_query = f"""
            SELECT 
                f.transaction_date as ngay,
                f.branch_code as chi_nhanh,
                f.product_code as ma_hang,
                p.product_name as ten_san_pham,
                p.category_level_1 as nhom_hang_cap_1,
                p.category_level_2 as nhom_hang_cap_2,
                f.gross_revenue as daily_revenue,
                f.quantity_sold as daily_quantity,
                f.gross_profit as daily_profit,
                f.transaction_count,
                p.brand as thuong_hieu,
                p.abc_class,
                0 as is_peak_day,
                1.0 as seasonal_factor,
                1.0 as revenue_factor,
                1.0 as quantity_factor,
                '' as peak_reason
            FROM retail_dw.fct_regular_sales f
            LEFT JOIN retail_dw.dim_product p ON f.product_code = p.p.product_code
            WHERE f.product_code IN ('{product_codes_str}')
              AND f.transaction_date >= today() - 60
            ORDER BY f.branch_code, f.product_code, f.transaction_date
            """
        
        history_df = self.ch.query(history_query)
        history_df['ngay'] = pd.to_datetime(history_df['ngay'])
        
        # VALIDATION: Chỉ giữ lại records có dữ liệu (giữ cả daily_quantity = 0)
        original_count = len(history_df)
        history_df = history_df[history_df['daily_quantity'].notna()]
        history_df = history_df[history_df['daily_revenue'].notna()]
        # KHÔNG filter > 0 để giữ lại ngày không bán hàng (daily_quantity = 0)
        # Model cần học được pattern "không bán hàng"
        
        filtered_count = len(history_df)
        if filtered_count < original_count:
            logger.warning(f"⚠️  Đã loại bỏ {original_count - filtered_count:,} records không có dữ liệu")
        
        # Fill NA cho các cột mới
        if 'thuong_hieu' in history_df.columns:
            history_df['thuong_hieu'] = history_df['thuong_hieu'].fillna('Unknown')
        if 'abc_class' in history_df.columns:
            history_df['abc_class'] = history_df['abc_class'].fillna('C')
        history_df['nhom_hang_cap_1'] = history_df['nhom_hang_cap_1'].fillna('Unknown')
        history_df['nhom_hang_cap_2'] = history_df['nhom_hang_cap_2'].fillna('Unknown')
        
        logger.info(f"✅ Đã tải {len(history_df):,} rows dữ liệu bán hàng thực tế từ fct_regular_sales")
        
        if len(history_df) == 0:
            logger.error("❌ Không có dữ liệu bán hàng hợp lệ cho các sản phẩm được chọn!")
            return pd.DataFrame()
        
        # BƯỚC 3: Tạo template cho future dates cho mỗi (chi_nhanh, ma_hang)
        logger.info("🔧 Đang tạo features cho dự báo...")
        
        # Lấy danh sách unique (chi_nhanh, ma_hang, ten_san_pham, categories)
        branch_products = history_df[['chi_nhanh', 'ma_hang', 'ten_san_pham', 'nhom_hang_cap_1', 'nhom_hang_cap_2']].drop_duplicates()
        
        # Tính category averages cho cold start fallback
        logger.info("📊 Tính category averages cho cold start fallback...")
        category_stats = history_df.groupby('nhom_hang_cap_1')['daily_quantity'].agg(['mean', 'median', 'std']).reset_index()
        category_stats_dict = category_stats.set_index('nhom_hang_cap_1')['median'].to_dict()
        
        # Kiểm tra phân phối dữ liệu theo ngày
        daily_counts = history_df.groupby('ngay').size()
        min_daily_records = daily_counts.min()
        max_daily_records = daily_counts.max()
        avg_daily_records = daily_counts.mean()
        
        logger.info(f"   📊 Daily data distribution:")
        logger.info(f"      - Min records/day: {min_daily_records}")
        logger.info(f"      - Max records/day: {max_daily_records}")
        logger.info(f"      - Avg records/day: {avg_daily_records:.1f}")
        
        if min_daily_records == 0:
            empty_days = daily_counts[daily_counts == 0].index.tolist()
            logger.warning(f"      ⚠️  {len(empty_days)} days have NO data!")
        elif min_daily_records < avg_daily_records * 0.5:
            logger.warning(f"      ⚠️  Some days have significantly fewer records than average")
        else:
            logger.info(f"      ✅ Good daily data distribution")
        
        forecasts = []
        cold_start_products = []
        model_features = list(self.models['product_quantity'].feature_names_in_)
        
        # BƯỚC 4: Xử lý từng (branch, product) trong memory (không query DB nữa)
        for _, bp in branch_products.iterrows():
            branch = bp['chi_nhanh']
            product = bp['ma_hang']
            product_name = bp['ten_san_pham']
            cat1 = bp['nhom_hang_cap_1']
            cat2 = bp['nhom_hang_cap_2']
            
            # Lấy lịch sử của sản phẩm này
            product_history = history_df[
                (history_df['chi_nhanh'] == branch) & 
                (history_df['ma_hang'] == product)
            ].sort_values('ngay').reset_index(drop=True)
            
            # COLD START HANDLING: Nếu ít hơn 2 ngày dữ liệu, dùng category median
            if len(product_history) < 2:
                cat_median = category_stats_dict.get(cat1, 10)  # Default 10 nếu không tìm thấy category
                cold_start_products.append({
                    'branch': branch,
                    'product': product,
                    'category': cat1,
                    'fallback_quantity': cat_median
                })
                
                # Tạo dự báo đơn giản dựa trên category median
                for future_date in future_dates:
                    month = future_date.month
                    sf = seasonal_map.get(month, {})
                    seasonal_factor = sf.get('seasonal_factor', 1.0)
                    
                    # Áp dụng seasonal factor vào category median
                    # cat_median đã là daily median, không cần chia 7
                    predicted_qty = max(0, cat_median * seasonal_factor)
                    
                    forecasts.append({
                        'forecast_date': future_date.date(),
                        'chi_nhanh': branch,
                        'ma_hang': product,
                        'ten_san_pham': product_name,
                        'nhom_hang_cap_1': cat1,
                        'nhom_hang_cap_2': cat2,
                        'abc_class': product_abc_map.get(product, 'Unknown'),
                        'predicted_quantity': round(predicted_qty),
                        'predicted_quantity_raw': float(predicted_qty),
                        'predicted_profit_margin': None,
                        'confidence_lower': predicted_qty * 0.5,
                        'confidence_upper': predicted_qty * 1.5,
                        'created_at': datetime.now(),
                        'is_cold_start': True  # Flag để đánh dấu
                    })
                continue  # Skip phần dự báo bình thường
            
            # Dự báo cho từng ngày trong tương lai (RECURSIVE FORECAST)
            # Sau mỗi ngày dự báo, cập nhật kết quả vào product_history để tính lag đúng
            predicted_values = {}  # Lưu các giá trị đã dự báo: {date: quantity}
            
            for future_date in future_dates:
                try:
                    # Lấy seasonal factors cho ngày này
                    month = future_date.month
                    sf = seasonal_map.get(month, {})
                    is_peak = 1 if sf.get('peak_reason') else 0
                    
                    # Cập nhật product_history với các giá trị đã dự báo trước đó trong tuần
                    # Điều này đảm bảo lag features được tính đúng
                    if predicted_values:
                        for pred_date, pred_qty in predicted_values.items():
                            # Tìm và cập nhật hoặc thêm vào product_history
                            mask = product_history['ngay'] == pred_date
                            if mask.any():
                                product_history.loc[mask, 'daily_quantity'] = pred_qty
                            else:
                                # Thêm row mới với giá trị dự báo
                                new_row = pd.DataFrame({
                                    'ngay': [pred_date],
                                    'chi_nhanh': [branch],
                                    'ma_hang': [product],
                                    'ten_san_pham': [product_name],
                                    'nhom_hang_cap_1': [cat1],
                                    'nhom_hang_cap_2': [cat2],
                                    'daily_quantity': [pred_qty],
                                    'daily_revenue': [0],  # Không dùng cho dự báo
                                    'daily_profit': [0],
                                    'transaction_count': [0],
                                    'is_peak_day': [is_peak],
                                    'seasonal_factor': [sf.get('seasonal_factor', 1.0)],
                                    'revenue_factor': [sf.get('revenue_factor', 1.0)],
                                    'quantity_factor': [sf.get('quantity_factor', 1.0)],
                                    'peak_reason': [sf.get('peak_reason', '')]
                                })
                                product_history = pd.concat([product_history, new_row], ignore_index=True)
                    
                    # Tạo row cho ngày cần dự báo (daily_quantity = 0, sẽ được dự báo)
                    future_row = pd.DataFrame({
                        'ngay': [future_date],
                        'chi_nhanh': [branch],
                        'ma_hang': [product],
                        'ten_san_pham': [product_name],
                        'nhom_hang_cap_1': [cat1],
                        'nhom_hang_cap_2': [cat2],
                        'daily_quantity': [0],  # Sẽ được dự báo
                        'daily_revenue': [0],
                        'daily_profit': [0],
                        'transaction_count': [0],
                        'is_peak_day': [is_peak],
                        'seasonal_factor': [sf.get('seasonal_factor', 1.0)],
                        'revenue_factor': [sf.get('revenue_factor', 1.0)],
                        'quantity_factor': [sf.get('quantity_factor', 1.0)],
                        'peak_reason': [sf.get('peak_reason', '')]
                    })
                    
                    # Kết hợp lịch sử (đã cập nhật với dự báo trước) + ngày cần dự báo
                    combined = pd.concat([product_history, future_row], ignore_index=True)
                    combined['ngay'] = pd.to_datetime(combined['ngay'])
                    combined = combined.sort_values('ngay').reset_index(drop=True)
                    
                    # Tạo features với prediction_mode=True (chỉ dùng lag >= 7)
                    combined_features = self.create_features(combined, prediction_mode=True)
                    
                    # Lấy row cho ngày cần dự báo
                    pred_row = combined_features[combined_features['ngay'] == future_date]
                    
                    if len(pred_row) == 0:
                        continue
                    
                    # Chuẩn bị features cho model (chỉ lấy các cột model cần)
                    X_pred = pd.DataFrame(0, index=[0], columns=model_features)
                    for col in model_features:
                        if col in pred_row.columns:
                            X_pred[col] = pred_row[col].fillna(0).values
                    
                    # Dự báo với Model 1 (Quantity) - clip để không âm
                    quantity_pred = max(0, self.models['product_quantity'].predict(X_pred)[0])
                    
                    # Lưu giá trị dự báo để dùng cho ngày tiếp theo (recursive)
                    predicted_values[future_date] = quantity_pred
                    
                    forecasts.append({
                        'forecast_date': future_date.date(),
                        'chi_nhanh': branch,
                        'ma_hang': product,
                        'ten_san_pham': product_name,
                        'nhom_hang_cap_1': cat1,
                        'nhom_hang_cap_2': cat2,
                        'abc_class': product_abc_map.get(product, 'Unknown'),
                        'predicted_quantity': round(quantity_pred),
                        'predicted_quantity_raw': float(quantity_pred),
                        'predicted_profit_margin': None,
                        'confidence_lower': quantity_pred * 0.8,
                        'confidence_upper': quantity_pred * 1.2,
                        'created_at': datetime.now()
                    })
                    
                except Exception as e:
                    logger.debug(f"Lỗi dự báo cho {branch}/{product} ngày {future_date}: {e}")
                    continue
        
        forecasts_df = pd.DataFrame(forecasts)
        
        if len(forecasts_df) > 0:
            logger.info(f"✅ Đã tạo {len(forecasts_df)} dự báo thành công")
            
            # Log cold start products
            if cold_start_products:
                cold_start_count = len(set([p['product'] for p in cold_start_products]))
                logger.info(f"⚠️  Cold start: {cold_start_count} sản phẩm dùng category median fallback")
                logger.info(f"   (Thiếu dữ liệu lịch sử, dùng trung vình ngành hàng)")
            
            # Thống kê theo ABC class
            if use_abc_filter and 'abc_class' in forecasts_df.columns:
                abc_stats = forecasts_df.groupby('abc_class').agg({
                    'predicted_quantity': 'sum'
                }).round(2)
                logger.info("📊 Tổng dự báo theo phân loại ABC:")
                for cls, row in abc_stats.iterrows():
                    logger.info(f"   Loại {cls}: {row['predicted_quantity']:,.0f} units")
            
            # Thống kê tổng quan
            total_predicted = forecasts_df['predicted_quantity'].sum()
            avg_predicted = forecasts_df['predicted_quantity'].mean()
            zero_predictions = (forecasts_df['predicted_quantity'] == 0).sum()
            cold_start_count = len(set([p['product'] for p in cold_start_products])) if cold_start_products else 0
            total_products = forecasts_df['ma_hang'].nunique()
            missing_data_pct = (cold_start_count / total_products * 100) if total_products > 0 else 0
            
            logger.info(f"📊 Tổng quan dự báo:")
            logger.info(f"   - Tổng số lượng dự báo: {total_predicted:,.0f} units")
            logger.info(f"   - Trung bình/sản phẩm: {avg_predicted:.1f} units")
            if zero_predictions > 0:
                logger.warning(f"   - ⚠️  Có {zero_predictions} dự báo = 0 (cần kiểm tra)")
            
            # Lưu data quality info cho email report
            self.data_quality = {
                'cold_start_count': cold_start_count,
                'fallback_used': cold_start_count > 0,
                'missing_data_pct': missing_data_pct,
                'zero_predictions': zero_predictions,
                'total_products': total_products,
                'data_age_days': 0  # TODO: Tính từ last transaction date
            }
        else:
            logger.warning("⚠️ Không có dự báo nào được tạo!")
        
        return forecasts_df
    
    def save_forecasts(self, forecasts: pd.DataFrame, send_email: bool = True):
        """Lưu dự báo vào database và gửi email thông báo"""
        # Tạo bảng nếu chưa có - Schema đầy đủ các cột
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS ml_forecasts (
            id SERIAL PRIMARY KEY,
            forecast_date DATE NOT NULL,
            chi_nhanh VARCHAR(100),
            ma_hang VARCHAR(50),
            ten_san_pham VARCHAR(500),
            nhom_hang_cap_1 VARCHAR(200),
            nhom_hang_cap_2 VARCHAR(200),
            abc_class VARCHAR(10),
            predicted_quantity FLOAT,
            predicted_quantity_raw FLOAT,
            predicted_revenue DECIMAL(15,2),
            predicted_profit_margin FLOAT,
            confidence_lower FLOAT,
            confidence_upper FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_forecasts_date ON ml_forecasts(forecast_date);
        CREATE INDEX IF NOT EXISTS idx_forecasts_product ON ml_forecasts(ma_hang);
        CREATE INDEX IF NOT EXISTS idx_forecasts_abc ON ml_forecasts(abc_class);
        """
        
        from sqlalchemy import text
        with self.pg.get_connection() as conn:
            # Thêm cột abc_class nếu bảng đã tồn tại nhưng chưa có cột này
            conn.execute(text("""
                ALTER TABLE ml_forecasts 
                ADD COLUMN IF NOT EXISTS abc_class VARCHAR(10),
                ADD COLUMN IF NOT EXISTS nhom_hang_cap_1 VARCHAR(200),
                ADD COLUMN IF NOT EXISTS nhom_hang_cap_2 VARCHAR(200);
            """))
            conn.commit()
            
            conn.execute(text(create_table_sql))
            conn.commit()  # Commit CREATE TABLE
            
            # Chỉ chọn các cột có trong bảng để insert
            db_columns = [
                'forecast_date', 'chi_nhanh', 'ma_hang', 'ten_san_pham',
                'nhom_hang_cap_1', 'nhom_hang_cap_2', 'abc_class',
                'predicted_quantity', 'predicted_quantity_raw', 'predicted_revenue',
                'predicted_profit_margin', 'confidence_lower', 'confidence_upper'
            ]
            # Lọc chỉ các cột tồn tại trong DataFrame
            available_cols = [col for col in db_columns if col in forecasts.columns]
            forecasts_to_save = forecasts[available_cols].copy()
            
            forecasts_to_save.to_sql('ml_forecasts', conn, if_exists='append', index=False)
            conn.commit()  # Commit INSERT
        
        logger.info(f"Saved {len(forecasts)} forecasts to database")
        
        # Gửi email thông báo kết quả dự báo
        if send_email and self.email_notifier and len(forecasts) > 0:
            try:
                # Log thông tin forecasts trước khi gửi email
                n_products = forecasts['ma_hang'].nunique() if 'ma_hang' in forecasts.columns else 0
                logger.info(f"📧 Đang gửi email forecast report với {len(forecasts)} records, {n_products} sản phẩm...")
                
                # CHẠY MODEL 2: Category Trend Forecast
                logger.info("📊 Chạy Model 2: Category Trend Forecast...")
                try:
                    category_forecasts = self.predict_category_trend(days=7)
                    if not category_forecasts.empty:
                        logger.info(f"✅ Model 2: {len(category_forecasts)} category forecasts")
                    else:
                        logger.warning("⚠️ Model 2: Không có dữ liệu dự báo")
                        category_forecasts = None
                except Exception as e:
                    logger.error(f"❌ Lỗi khi chạy Model 2: {e}")
                    category_forecasts = None
                
                # THÊM DỮ LIỆU BÁN TUẦN TRƯỚC cho email report
                logger.info("📊 Query doanh số tuần trước cho email report...")
                try:
                    product_list = forecasts['ma_hang'].unique().tolist()
                    products_str = "', '".join(str(p) for p in product_list)
                    
                    # Lấy tuần mới nhất có dữ liệu để tính "tuần trước" chính xác
                    # Query tất cả các tuần có dữ liệu, sắp xếp theo năm-tuần giảm dần
                    current_week_query = """
                    SELECT DISTINCT
                        toYear(transaction_date) as year,
                        toWeek(transaction_date) as week
                    FROM retail_dw.fct_regular_sales
                    ORDER BY year DESC, week DESC
                    LIMIT 2
                    """
                    week_result = self.ch.query(current_week_query)
                    if week_result is not None and len(week_result) >= 2:
                        # Tuần mới nhất có dữ liệu
                        current_week = int(week_result.iloc[0]['week'])
                        current_year = int(week_result.iloc[0]['year'])
                        # Tuần trước (tuần thứ 2 trong kết quả)
                        last_week = int(week_result.iloc[1]['week'])
                        last_year = int(week_result.iloc[1]['year'])
                        logger.info(f"   Tuần gần nhất có dữ liệu: {current_year}-W{current_week:02d}")
                        logger.info(f"   Tuần trước (so sánh): {last_year}-W{last_week:02d}")
                    elif week_result is not None and len(week_result) == 1:
                        # Chỉ có 1 tuần dữ liệu, dùng tuần đó làm tuần trước
                        last_week = int(week_result.iloc[0]['week'])
                        last_year = int(week_result.iloc[0]['year'])
                        logger.warning(f"   Chỉ có 1 tuần dữ liệu: {last_year}-W{last_week:02d}")
                    else:
                        # Fallback: dùng 7 ngày trước
                        logger.warning("   Không lấy được tuần dữ liệu, dùng 7 ngày gần nhất")
                        last_week = None
                    
                    # Query theo tuần hoặc 7 ngày gần nhất
                    if last_week is not None:
                        # Query theo tuần (từ thứ 2 đến chủ nhật tuần trước)
                        last_week_query = f"""
                        SELECT 
                            f.product_code as ma_hang,
                            SUM(f.quantity_sold) as last_week_sales
                        FROM retail_dw.fct_regular_sales f
                        WHERE f.product_code IN ('{products_str}')
                          AND toYear(f.transaction_date) = {last_year}
                          AND toWeek(f.transaction_date) = {last_week}
                        GROUP BY f.product_code
                        """
                        logger.info(f"   Query tuần {last_year}-W{last_week:02d}")
                    else:
                        # Fallback: 7 ngày gần nhất có dữ liệu
                        last_week_query = f"""
                        SELECT 
                            f.product_code as ma_hang,
                            SUM(f.quantity_sold) as last_week_sales
                        FROM retail_dw.fct_regular_sales f
                        WHERE f.product_code IN ('{products_str}')
                          AND f.transaction_date >= (
                              SELECT MAX(transaction_date) - INTERVAL 7 DAY 
                              FROM retail_dw.fct_regular_sales
                          )
                          AND f.transaction_date < (
                              SELECT MAX(transaction_date) 
                              FROM retail_dw.fct_regular_sales
                          )
                        GROUP BY f.product_code
                        """
                        logger.info("   Query 7 ngày gần nhất có dữ liệu")
                    
                    last_week_df = self.ch.query(last_week_query)
                    
                    if not last_week_df.empty:
                        forecasts = forecasts.merge(
                            last_week_df[['ma_hang', 'last_week_sales']], 
                            on='ma_hang', 
                            how='left'
                        )
                        forecasts['last_week_sales'] = forecasts['last_week_sales'].fillna(0)
                        logger.info(f"✅ Đã thêm last_week_sales cho {len(last_week_df)} sản phẩm")
                    else:
                        logger.warning("⚠️ Không có dữ liệu bán tuần trước")
                        forecasts['last_week_sales'] = 0
                except Exception as e:
                    logger.warning(f"⚠️ Không thể lấy dữ liệu tuần trước: {e}")
                    forecasts['last_week_sales'] = 0
                
                # === LỌC VÀ SẮP XẾP THEO YÊU CẦU MỚI ===
                logger.info("📊 Áp dụng logic lọc và sắp xếp mới...")
                try:
                    # 1. Query doanh số 4 tuần gần nhất cho từng sản phẩm
                    products_str = "', '".join(str(p) for p in forecasts['ma_hang'].unique())
                    sales_4weeks_query = f"""
                    SELECT 
                        product_code as ma_hang,
                        SUM(quantity_sold) as sales_4weeks
                    FROM retail_dw.fct_regular_sales
                    WHERE product_code IN ('{products_str}')
                      AND transaction_date >= today() - INTERVAL 28 DAY
                    GROUP BY product_code
                    """
                    sales_4weeks_df = self.ch.query(sales_4weeks_query)
                    
                    if not sales_4weeks_df.empty:
                        forecasts = forecasts.merge(
                            sales_4weeks_df[['ma_hang', 'sales_4weeks']], 
                            on='ma_hang', 
                            how='left'
                        )
                        forecasts['sales_4weeks'] = pd.to_numeric(forecasts['sales_4weeks'], errors='coerce').fillna(0)
                        
                        # 2. Loại bỏ sản phẩm A-class không có doanh số trong 4 tuần
                        original_count = len(forecasts)
                        if 'abc_class' in forecasts.columns:
                            # Đảm bảo abc_class là string
                            forecasts['abc_class'] = forecasts['abc_class'].astype(str)
                            # Giữ lại: B-class, C-class, hoặc A-class có sales_4weeks > 0
                            mask_keep = (
                                (forecasts['abc_class'].isin(['B', 'C'])) | 
                                ((forecasts['abc_class'] == 'A') & (forecasts['sales_4weeks'] > 0))
                            )
                            removed_a_class = forecasts[(forecasts['abc_class'] == 'A') & (forecasts['sales_4weeks'] == 0)]
                            if len(removed_a_class) > 0:
                                logger.info(f"   🗑️  Loại bỏ {len(removed_a_class)} sản phẩm A-class không có doanh số 4 tuần qua")
                            forecasts = forecasts[mask_keep].copy()
                        
                        logger.info(f"   📊 Còn lại {len(forecasts)}/{original_count} sản phẩm sau khi lọc")
                    
                    # 3. Query tồn kho nhỏ nhất (ton_kho_nho_nhat)
                    inventory_query = f"""
                    SELECT 
                        p.product_code as ma_hang,
                        MIN(i.ton_kho) as ton_kho_nho_nhat
                    FROM retail_dw.dim_product p
                    LEFT JOIN (
                        SELECT product_code, MIN(stock_quantity) as ton_kho
                        FROM retail_dw.staging_inventory_transactions
                        WHERE snapshot_date >= today() - INTERVAL 7 DAY
                        GROUP BY product_code
                    ) i ON p.product_code = i.product_code
                    WHERE p.product_code IN ('{products_str}')
                    GROUP BY p.product_code
                    """
                    try:
                        inventory_df = self.ch.query(inventory_query)
                        if not inventory_df.empty:
                            forecasts = forecasts.merge(
                                inventory_df[['ma_hang', 'ton_kho_nho_nhat']], 
                                on='ma_hang', 
                                how='left'
                            )
                            forecasts['ton_kho_nho_nhat'] = forecasts['ton_kho_nho_nhat'].fillna(0)
                        else:
                            forecasts['ton_kho_nho_nhat'] = 0
                    except Exception as e:
                        logger.warning(f"   ⚠️ Không lấy được dữ liệu tồn kho: {e}")
                        forecasts['ton_kho_nho_nhat'] = 0
                    
                    # 4. Đảm bảo numeric type trước khi sắp xếp
                    forecasts['last_week_sales'] = pd.to_numeric(forecasts['last_week_sales'], errors='coerce').fillna(0)
                    forecasts['ton_kho_nho_nhat'] = pd.to_numeric(forecasts['ton_kho_nho_nhat'], errors='coerce').fillna(0)
                    
                    # 5. Sắp xếp: last_week_sales DESC, rồi ton_kho_nho_nhat ASC
                    forecasts = forecasts.sort_values(
                        by=['last_week_sales', 'ton_kho_nho_nhat'], 
                        ascending=[False, True]
                    ).reset_index(drop=True)
                    
                    logger.info(f"   ✅ Đã sắp xếp: 1) Bán tuần trước (cao→thấp) 2) Tồn kho nhỏ nhất (thấp→cao)")
                    
                    # Log top 10 unique products sau khi sắp xếp (forecasts có nhiều dòng cho cùng 1 product)
                    unique_products = forecasts.drop_duplicates(subset=['ma_hang']).head(10)
                    logger.info(f"   📋 Top 10 sản phẩm sau sắp xếp:")
                    for idx, row in unique_products.iterrows():
                        logger.info(f"      {row['ma_hang']} | {row['ten_san_pham'][:25]:<25} | Bán T-{row['last_week_sales']:>4.0f} | Tồn {row['ton_kho_nho_nhat']:>4.0f} | {row['abc_class']}")
                    
                    # Thống kê số sản phẩm có last_week_sales > 0
                    n_with_sales = (forecasts.drop_duplicates(subset=['ma_hang'])['last_week_sales'] > 0).sum()
                    n_total = forecasts['ma_hang'].nunique()
                    logger.info(f"   📊 Thống kê: {n_with_sales}/{n_total} sản phẩm có bán tuần trước > 0")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Lỗi khi áp dụng logic lọc/sắp xếp: {e}")
                
                # Lấy một số khuyến nghị tồn kho cho top products
                inventory_recs = []
                if 'ma_hang' in forecasts.columns:
                    top_products = forecasts.groupby('ma_hang')['predicted_quantity'].sum().sort_values(ascending=False).head(10)
                    logger.info(f"   Top 10 products for inventory recommendations: {list(top_products.head(10).index)}")
                    for product_code in top_products.index:
                        try:
                            rec = self.get_inventory_recommendations(product_code)
                            if 'error' not in rec:
                                inventory_recs.append(rec)
                        except Exception as e:
                            logger.debug(f"   Could not get inventory rec for {product_code}: {e}")
                    logger.info(f"   Got {len(inventory_recs)} inventory recommendations")
                
                # Tạo file đơn hàng Excel đính kèm
                logger.info("📦 Đang tạo file đơn hàng Excel...")
                try:
                    po_file_path = self.generate_purchase_order_excel(
                        forecasts=forecasts,
                        top_n=50
                    )
                    logger.info(f"✅ Đã tạo file đơn hàng: {po_file_path}")
                except Exception as e:
                    logger.error(f"❌ Lỗi khi tạo file đơn hàng: {e}")
                    po_file_path = None
                
                success = self.email_notifier.send_forecast_report(
                    forecasts=forecasts,
                    inventory_recommendations=inventory_recs,
                    model_dir=self.model_dir,
                    purchase_order_file=po_file_path,
                    category_forecasts=category_forecasts
                )
                if success:
                    logger.info("✅ Đã gửi email forecast report thành công")
                else:
                    logger.warning("⚠️ Không thể gửi email forecast report")
            except Exception as e:
                logger.error(f"❌ Lỗi khi gửi email forecast: {e}")
    
    def predict_category_trend(self, days: int = 7) -> pd.DataFrame:
        """
        Model 2: Dự báo xu hướng theo Category Level
        
        Dự báo tổng quantity của từng nhóm hàng cấp 1, sử dụng aggregate features
        và seasonal patterns. So sánh với Model 1 để đánh giá consistency.
        
        Args:
            days: Số ngày dự báo (mặc định 7)
            
        Returns:
            DataFrame với dự báo category-level
        """
        logger.info("=" * 60)
        logger.info("📊 MODEL 2: CATEGORY TREND FORECAST")
        logger.info("=" * 60)
        
        # Load models nếu chưa có
        if 'category_trend' not in self.models:
            model_path = os.path.join(self.model_dir, 'category_trend_model.pkl')
            if os.path.exists(model_path):
                self.models['category_trend'] = joblib.load(model_path)
                logger.info("✅ Loaded category_trend model")
            else:
                logger.error("❌ Model category_trend chưa được train!")
                return pd.DataFrame()
        
        # Tạo future dates
        future_dates = pd.date_range(
            start=datetime.now().date() + timedelta(days=1),
            periods=days,
            freq='D'
        )
        
        # Lấy danh sách categories
        categories_query = """
        SELECT DISTINCT category_level_1 as nhom_hang_cap_1
        FROM retail_dw.dim_product
        WHERE category_level_1 IS NOT NULL
          AND lower(category_level_1) NOT LIKE '%khuyến mại%'
          AND lower(category_level_1) NOT LIKE '%khuyen mai%'
        ORDER BY category_level_1
        """
        try:
            categories = self.ch.query(categories_query)
            category_list = categories['nhom_hang_cap_1'].tolist()
        except Exception as e:
            logger.error(f"❌ Lỗi khi lấy danh sách categories: {e}")
            return pd.DataFrame()
        
        logger.info(f"📦 Categories: {len(category_list)}")
        logger.info(f"📅 Forecast period: {future_dates[0]} to {future_dates[-1]}")
        
        # Lấy dynamic seasonal factors
        check_query = """
        SELECT count() 
        FROM system.tables 
        WHERE database = 'retail_dw' AND name = 'int_dynamic_seasonal_factor'
        """
        try:
            seasonal_exists = self.ch.query(check_query).iloc[0, 0] > 0
        except:
            seasonal_exists = False
        
        seasonal_map = {}
        if seasonal_exists:
            future_months = list(set([d.month for d in future_dates]))
            months_str = ', '.join([str(m) for m in future_months])
            
            seasonal_query = f"""
            SELECT 
                month,
                argMax(peak_reason, calculated_at) as peak_reason,
                argMax(seasonal_factor, calculated_at) as seasonal_factor,
                argMax(quantity_factor, calculated_at) as quantity_factor,
                argMax(is_peak_day, calculated_at) as is_peak_day
            FROM retail_dw.int_dynamic_seasonal_factor
            WHERE month IN ({months_str})
            GROUP BY month
            """
            try:
                seasonal_df = self.ch.query(seasonal_query)
                for _, row in seasonal_df.iterrows():
                    seasonal_map[int(row['month'])] = {
                        'seasonal_factor': float(row.get('seasonal_factor', 1.0)),
                        'quantity_factor': float(row.get('quantity_factor', 1.0)),
                        'is_peak_day': int(row.get('is_peak_day', 0)),
                        'peak_reason': row.get('peak_reason', '')
                    }
                logger.info(f"✅ Loaded seasonal factors: {len(seasonal_map)} months")
            except Exception as e:
                logger.warning(f"⚠️ Không thể load seasonal factors: {e}")
        
        # Lấy dữ liệu lịch sử category-level
        cats_str = "', '".join(category_list)
        history_query = f"""
        SELECT 
            f.transaction_date as ngay,
            p.category_level_1 as nhom_hang_cap_1,
            SUM(f.quantity_sold) as daily_quantity,
            SUM(f.gross_revenue) as daily_revenue,
            toDayOfWeek(f.transaction_date) as day_of_week,
            toDayOfMonth(f.transaction_date) as day_of_month,
            toMonth(f.transaction_date) as month,
            toWeek(f.transaction_date) as week_of_year,
            toDayOfWeek(f.transaction_date) IN (6, 7) as is_weekend,
            multiIf(
                (toMonth(f.transaction_date) = 1 AND toDayOfMonth(f.transaction_date) <= 5), true,
                (toMonth(f.transaction_date) = 4 AND toDayOfMonth(f.transaction_date) = 30), true,
                (toMonth(f.transaction_date) = 5 AND toDayOfMonth(f.transaction_date) = 1), true,
                (toMonth(f.transaction_date) = 9 AND toDayOfMonth(f.transaction_date) = 2), true,
                false
            ) as is_holiday
        FROM retail_dw.fct_regular_sales f
        LEFT JOIN retail_dw.dim_product p ON f.product_code = p.p.product_code
        WHERE p.category_level_1 IN ('{cats_str}')
          AND f.transaction_date >= today() - 60
          AND f.product_code IS NOT NULL
          AND f.product_code != ''
          AND f.quantity_sold > 0
        GROUP BY 
            f.transaction_date, 
            p.category_level_1,
            toDayOfWeek(f.transaction_date),
            toDayOfMonth(f.transaction_date),
            toMonth(f.transaction_date),
            toWeek(f.transaction_date),
            is_weekend,
            is_holiday
        ORDER BY p.category_level_1, f.transaction_date
        """
        
        try:
            history_df = self.ch.query(history_query)
            history_df['ngay'] = pd.to_datetime(history_df['ngay'])
            
            # VALIDATION: Chỉ giữ lại records có dữ liệu bán thực tế
            original_count = len(history_df)
            history_df = history_df[history_df['daily_quantity'] > 0]
            history_df = history_df[history_df['daily_revenue'] > 0]
            
            if len(history_df) < original_count:
                logger.warning(f"⚠️  Đã loại bỏ {original_count - len(history_df)} category-records không có dữ liệu bán hàng")
            
            logger.info(f"✅ Loaded {len(history_df)} historical category records with actual sales")
        except Exception as e:
            logger.error(f"❌ Lỗi khi query category history: {e}")
            return pd.DataFrame()
        
        # Dự báo cho từng category
        forecasts = []
        model_features = list(self.models['category_trend'].feature_names_in_)
        
        for category in category_list:
            cat_history = history_df[history_df['nhom_hang_cap_1'] == category].sort_values('ngay')
            
            if len(cat_history) < 7:
                logger.warning(f"⚠️ Category {category}: insufficient data ({len(cat_history)} days)")
                continue
            
            for future_date in future_dates:
                try:
                    # Tạo future row
                    month = future_date.month
                    sf = seasonal_map.get(month, {'seasonal_factor': 1.0, 'quantity_factor': 1.0, 'is_peak_day': 0})
                    
                    future_row = pd.DataFrame({
                        'ngay': [future_date],
                        'nhom_hang_cap_1': [category],
                        'daily_quantity': [0],
                        'daily_revenue': [0],
                        'is_peak_day': [sf['is_peak_day']],
                        'seasonal_factor': [sf['seasonal_factor']],
                        'quantity_factor': [sf['quantity_factor']]
                    })
                    
                    # Combine và tạo features
                    combined = pd.concat([cat_history, future_row], ignore_index=True)
                    combined['ngay'] = pd.to_datetime(combined['ngay'])
                    
                    # Tạo time-based features
                    combined['day_of_week'] = combined['ngay'].dt.dayofweek + 1
                    combined['day_of_month'] = combined['ngay'].dt.day
                    combined['month'] = combined['ngay'].dt.month
                    combined['week_of_year'] = combined['ngay'].dt.isocalendar().week.astype(int)
                    combined['is_weekend'] = (combined['day_of_week'] >= 6).astype(int)
                    combined['is_month_start'] = (combined['day_of_month'] == 1).astype(int)
                    combined['is_month_end'] = (combined['day_of_month'] == combined['ngay'].dt.days_in_month).astype(int)
                    
                    # Holiday detection
                    combined['is_holiday'] = (
                        ((combined['month'] == 1) & (combined['day_of_month'] <= 5)) |
                        ((combined['month'] == 4) & (combined['day_of_month'] == 30)) |
                        ((combined['month'] == 5) & (combined['day_of_month'] == 1)) |
                        ((combined['month'] == 9) & (combined['day_of_month'] == 2))
                    ).astype(int)
                    
                    # Lag features
                    for lag in [1, 7, 14]:
                        combined[f'lag_{lag}_quantity'] = combined['daily_quantity'].shift(lag)
                        combined[f'lag_{lag}_revenue'] = combined['daily_revenue'].shift(lag)
                    
                    # Rolling statistics
                    for window in [7, 14]:
                        combined[f'rolling_mean_{window}_quantity'] = combined['daily_quantity'] \
                            .rolling(window, min_periods=1).mean()
                    
                    # Growth rate
                    combined['quantity_growth'] = combined['daily_quantity'].pct_change()
                    combined['quantity_growth'] = combined['quantity_growth'].replace([np.inf, -np.inf], 0).fillna(0)
                    
                    # Encoding
                    combined['category1_encoded'] = pd.Categorical(combined['nhom_hang_cap_1']).codes
                    
                    # Dummy values cho compatibility
                    combined['chi_nhanh'] = 'ALL_BRANCHES'
                    combined['ma_hang'] = 'ALL_PRODUCTS'
                    combined['nhom_hang_cap_2'] = 'ALL_CAT2'
                    combined['branch_encoded'] = 0
                    combined['category2_encoded'] = 0
                    combined['category_daily_quantity'] = combined['daily_quantity']
                    
                    # Clean up
                    numeric_cols = combined.select_dtypes(include=[np.number]).columns
                    for col in numeric_cols:
                        combined[col] = combined[col].replace([np.inf, -np.inf], 0).fillna(0)
                    
                    # Fill missing features
                    for col in model_features:
                        if col not in combined.columns:
                            combined[col] = 0
                    
                    # Lấy row dự báo
                    pred_row = combined[combined['ngay'] == future_date]
                    if len(pred_row) == 0:
                        continue
                    
                    # Predict
                    X_pred = pred_row[model_features].fillna(0)
                    quantity_pred = max(0, self.models['category_trend'].predict(X_pred)[0])
                    
                    forecasts.append({
                        'forecast_date': future_date.date(),
                        'nhom_hang_cap_1': category,
                        'predicted_quantity': round(quantity_pred),
                        'predicted_quantity_raw': float(quantity_pred),
                        'seasonal_factor': sf['seasonal_factor'],
                        'is_peak_day': sf['is_peak_day'],
                        'peak_reason': sf.get('peak_reason', ''),
                        'created_at': datetime.now()
                    })
                    
                except Exception as e:
                    logger.debug(f"Lỗi dự báo category {category} ngày {future_date}: {e}")
        
        result_df = pd.DataFrame(forecasts)
        logger.info(f"✅ Model 2: {len(result_df)} category-level forecasts generated")
        
        # Tổng hợp theo category
        if not result_df.empty:
            summary = result_df.groupby('nhom_hang_cap_1')['predicted_quantity'].sum().sort_values(ascending=False)
            logger.info("\n📊 Category Forecast Summary (7 days total):")
            for cat, qty in summary.head(10).items():
                logger.info(f"   {cat}: {qty:,.0f} units")
        
        return result_df
    
    def compare_model_predictions(self, product_forecasts: pd.DataFrame, 
                                   category_forecasts: pd.DataFrame) -> Dict:
        """
        So sánh dự báo giữa Model 1 (Product-level) và Model 2 (Category-level)
        
        Tính consistency score và phát hiện sự khác biệt đáng chú ý.
        
        Args:
            product_forecasts: Kết quả từ predict_next_week() [Model 1]
            category_forecasts: Kết quả từ predict_category_trend() [Model 2]
            
        Returns:
            Dict chứa comparison metrics và analysis
        """
        logger.info("=" * 60)
        logger.info("📊 MODEL COMPARISON: Product vs Category Level")
        logger.info("=" * 60)
        
        if product_forecasts.empty or category_forecasts.empty:
            logger.warning("⚠️ Thiếu dữ liệu dự báo để so sánh")
            return {'error': 'Insufficient forecast data'}
        
        # Aggregate Model 1 lên category level để so sánh
        model1_by_category = product_forecasts.groupby('nhom_hang_cap_1').agg({
            'predicted_quantity': 'sum',
            'ma_hang': 'nunique'
        }).rename(columns={'ma_hang': 'num_products'})
        
        # Model 2 đã ở category level
        model2_by_category = category_forecasts.groupby('nhom_hang_cap_1')['predicted_quantity'].sum()
        
        # Tính tổng tất cả categories
        total_model1 = model1_by_category['predicted_quantity'].sum()
        total_model2 = model2_by_category.sum()
        
        logger.info(f"\n📈 TỔNG DỰ BÁO (7 ngày):")
        logger.info(f"   Model 1 (Product-level):  {total_model1:,.0f} units")
        logger.info(f"   Model 2 (Category-level): {total_model2:,.0f} units")
        
        # Tính overall deviation
        if total_model1 > 0:
            overall_deviation = abs(total_model2 - total_model1) / total_model1 * 100
            logger.info(f"   Overall Deviation: {overall_deviation:.1f}%")
        
        # So sánh từng category
        comparison = []
        all_categories = set(model1_by_category.index) | set(model2_by_category.index)
        
        logger.info(f"\n📊 CHI TIẾT THEO CATEGORY:")
        logger.info(f"{'Category':<30} {'Model 1':<12} {'Model 2':<12} {'Diff %':<10} {'Status'}")
        logger.info("-" * 80)
        
        for cat in sorted(all_categories):
            m1_qty = model1_by_category.loc[cat, 'predicted_quantity'] if cat in model1_by_category.index else 0
            m2_qty = model2_by_category.loc[cat] if cat in model2_by_category.index else 0
            num_products = model1_by_category.loc[cat, 'num_products'] if cat in model1_by_category.index else 0
            
            if m1_qty > 0:
                diff_pct = (m2_qty - m1_qty) / m1_qty * 100
            else:
                diff_pct = 0 if m2_qty == 0 else float('inf')
            
            # Đánh giá consistency
            if abs(diff_pct) <= 10:
                status = "✅ Consistent"
            elif abs(diff_pct) <= 25:
                status = "⚠️ Warning"
            else:
                status = "🔴 Significant Diff"
            
            comparison.append({
                'category': cat,
                'model1_quantity': m1_qty,
                'model2_quantity': m2_qty,
                'difference_pct': diff_pct,
                'num_products': num_products,
                'status': status
            })
            
            logger.info(f"{cat:<30} {m1_qty:>11,.0f} {m2_qty:>11,.0f} {diff_pct:>+9.1f}% {status}")
        
        # Tính consistency score
        consistent_cats = sum(1 for c in comparison if "Consistent" in c['status'])
        total_cats = len(comparison)
        consistency_score = consistent_cats / total_cats * 100 if total_cats > 0 else 0
        
        logger.info(f"\n📊 CONSISTENCY SCORE: {consistency_score:.1f}%")
        logger.info(f"   Consistent categories: {consistent_cats}/{total_cats}")
        
        return {
            'total_model1': total_model1,
            'total_model2': total_model2,
            'overall_deviation_pct': overall_deviation if total_model1 > 0 else None,
            'consistency_score': consistency_score,
            'category_comparison': comparison,
            'recommendation': 'High consistency' if consistency_score >= 80 else 
                             'Moderate consistency - review significant differences' if consistency_score >= 60 else
                             'Low consistency - investigate data quality'
        }
    
    def validate_forecast_accuracy(self, days_back: int = 7) -> Dict:
        """
        Validate độ chính xác của model bằng cách so sánh dự báo với dữ liệu thực tế
        
        Lấy dự báo từ X ngày trước (cho X ngày tiếp theo) và so sánh với 
        dữ liệu bán hàng thực tế trong X ngày đó.
        
        Args:
            days_back: Số ngày lùi lại để validation (mặc định 7)
            
        Returns:
            Dict chứa accuracy metrics
        """
        logger.info("=" * 70)
        logger.info(f"📊 VALIDATION: Kiểm tra độ chính xác model ({days_back} ngày)")
        logger.info("=" * 70)
        
        try:
            # Lấy dữ liệu bán hàng thực tế trong 7 ngày gần nhất
            actual_query = f"""
            SELECT 
                transaction_date,
                product_code as ma_hang,
                SUM(quantity_sold) as actual_quantity,
                SUM(gross_revenue) as actual_revenue
            FROM retail_dw.fct_regular_sales
            WHERE transaction_date >= today() - INTERVAL {days_back} DAY
              AND transaction_date < today()
            GROUP BY transaction_date, product_code
            ORDER BY transaction_date, product_code
            """
            
            actual_df = self.ch.query(actual_query)
            
            if actual_df.empty:
                logger.warning(f"⚠️ Không có dữ liệu bán hàng thực tế trong {days_back} ngày gần nhất")
                return {'error': 'No actual sales data available'}
            
            logger.info(f"✅ Đã lấy {len(actual_df)} records dữ liệu thực tế")
            logger.info(f"   Ngày: {actual_df['transaction_date'].min()} đến {actual_df['transaction_date'].max()}")
            logger.info(f"   Số sản phẩm: {actual_df['ma_hang'].nunique()}")
            logger.info(f"   Tổng số lượng bán thực tế: {actual_df['actual_quantity'].sum():,.0f}")
            logger.info(f"   Tổng doanh thu thực tế: {actual_df['actual_revenue'].sum():,.0f}")
            
            # Lấy dự báo từ X ngày trước cho X ngày tiếp theo
            forecast_query = f"""
            SELECT 
                forecast_date,
                ma_hang,
                predicted_quantity,
                predicted_revenue,
                ten_san_pham
            FROM ml_forecasts
            WHERE forecast_date >= CURRENT_DATE - INTERVAL '{days_back * 2} days'
              AND forecast_date < CURRENT_DATE - INTERVAL '{days_back} days'
              AND created_at < CURRENT_DATE - INTERVAL '{days_back} days'
            ORDER BY forecast_date, ma_hang
            """
            
            try:
                from sqlalchemy import text
                with self.pg.get_connection() as conn:
                    forecast_df = pd.read_sql(text(forecast_query), conn)
            except Exception as e:
                logger.warning(f"⚠️ Không thể lấy dữ liệu dự báo cũ: {e}")
                forecast_df = pd.DataFrame()
            
            if forecast_df.empty:
                logger.info(f"📊 CHỈ CÓ DỮ LIỆU THỰC TẾ (không có dự báo cũ để so sánh)")
                logger.info(f"   → Sử dụng để tính baseline metrics")
                
                # Tính các chỉ số cơ bản từ dữ liệu thực tế
                daily_totals = actual_df.groupby('transaction_date')['actual_quantity'].sum()
                
                return {
                    'validation_type': 'baseline_only',
                    'days_analyzed': days_back,
                    'actual_total_quantity': int(actual_df['actual_quantity'].sum()),
                    'actual_total_revenue': float(actual_df['actual_revenue'].sum()),
                    'actual_avg_daily': float(daily_totals.mean()),
                    'actual_std_daily': float(daily_totals.std()),
                    'num_products': actual_df['ma_hang'].nunique(),
                    'date_range': {
                        'start': str(actual_df['transaction_date'].min()),
                        'end': str(actual_df['transaction_date'].max())
                    },
                    'top_products': actual_df.groupby('ma_hang')['actual_quantity'].sum()
                        .sort_values(ascending=False).head(10).to_dict()
                }
            
            # Nếu có cả dự báo và thực tế, tính accuracy metrics
            logger.info(f"✅ Đã lấy {len(forecast_df)} records dự báo cũ")
            
            # Merge dự báo và thực tế
            comparison = pd.merge(
                forecast_df, 
                actual_df,
                left_on=['forecast_date', 'ma_hang'],
                right_on=['transaction_date', 'ma_hang'],
                how='inner'
            )
            
            if comparison.empty:
                logger.warning("⚠️ Không có sản phẩm nào match giữa dự báo và thực tế")
                return {'error': 'No matching products between forecast and actual'}
            
            # Tính accuracy metrics
            comparison['error'] = comparison['predicted_quantity'] - comparison['actual_quantity']
            comparison['abs_error'] = comparison['error'].abs()
            comparison['pct_error'] = (comparison['error'] / comparison['actual_quantity'] * 100).replace([np.inf, -np.inf], np.nan)
            comparison['abs_pct_error'] = comparison['pct_error'].abs()
            
            # Overall metrics
            mae = comparison['abs_error'].mean()
            rmse = np.sqrt((comparison['error'] ** 2).mean())
            mape = comparison['abs_pct_error'].mean()
            
            # MdAPE
            valid_pct_errors = comparison['abs_pct_error'].dropna()
            mdape = valid_pct_errors.median() if len(valid_pct_errors) > 0 else np.nan
            
            logger.info(f"\n📊 ACCURACY METRICS (so sánh dự báo vs thực tế):")
            logger.info(f"   MAE:  {mae:.2f} units")
            logger.info(f"   RMSE: {rmse:.2f} units")
            logger.info(f"   MAPE: {mape:.2f}%")
            logger.info(f"   MdAPE: {mdape:.2f}% ⭐")
            logger.info(f"   Số records so sánh: {len(comparison)}")
            
            # Top sản phẩm có sai số lớn nhất
            top_errors = comparison.nlargest(10, 'abs_error')[
                ['ma_hang', 'ten_san_pham', 'predicted_quantity', 'actual_quantity', 'error', 'abs_pct_error']
            ]
            
            logger.info(f"\n🔴 Top 10 sản phẩm có sai số lớn nhất:")
            for _, row in top_errors.iterrows():
                logger.info(f"   {row['ma_hang']}: Dự báo {row['predicted_quantity']:.0f}, "
                          f"Thực tế {row['actual_quantity']:.0f}, "
                          f"Sai số {row['error']:+.0f} ({row['abs_pct_error']:.1f}%)")
            
            return {
                'validation_type': 'forecast_vs_actual',
                'days_analyzed': days_back,
                'metrics': {
                    'mae': float(mae),
                    'rmse': float(rmse),
                    'mape': float(mape),
                    'mdape': float(mdape)
                },
                'comparison_summary': {
                    'total_forecast': float(comparison['predicted_quantity'].sum()),
                    'total_actual': float(comparison['actual_quantity'].sum()),
                    'overall_bias': float(comparison['predicted_quantity'].sum() - comparison['actual_quantity'].sum()),
                    'num_records': len(comparison),
                    'num_products': comparison['ma_hang'].nunique()
                },
                'top_errors': top_errors.to_dict('records')
            }
            
        except Exception as e:
            logger.error(f"❌ Lỗi khi validation: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e)}
    
    def get_inventory_recommendations(self, product_code: str) -> Dict:
        """Đưa ra khuyến nghị tồn kho"""
        # Lấy dự báo cho sản phẩm
        forecast_query = f"""
        SELECT 
            SUM(predicted_quantity) as total_predicted,
            AVG(predicted_quantity) as avg_daily
        FROM ml_forecasts
        WHERE ma_hang = '{product_code}'
        AND forecast_date >= CURRENT_DATE
        AND forecast_date <= CURRENT_DATE + INTERVAL '7 days'
        """
        
        forecast = self.pg.execute_query(forecast_query)
        
        if forecast.empty:
            return {'error': 'No forecast available'}
        
        total_predicted = forecast['total_predicted'].iloc[0]
        avg_daily = forecast['avg_daily'].iloc[0]
        
        # Kiểm tra giá trị NULL
        if pd.isna(total_predicted) or pd.isna(avg_daily):
            return {'error': 'Invalid forecast data'}
        
        # Khuyến nghị
        return {
            'product_code': product_code,
            'predicted_next_7_days': total_predicted,
            'avg_daily_demand': avg_daily,
            'recommended_safety_stock': round(avg_daily * 7 * 1.5),  # 7 days * safety factor
            'reorder_point': round(avg_daily * 14),  # 2 weeks
            'suggested_order_quantity': round(avg_daily * 30),  # 1 month
            'reorder_urgency': 'High' if total_predicted > avg_daily * 14 else 'Normal'
        }
    
    def generate_purchase_order_csv(self, forecasts: pd.DataFrame = None, 
                                     top_n: int = 50,
                                     output_path: str = None,
                                     lead_time_max: int = 7,
                                     lead_time_avg: int = 5) -> str:
        """
        Tạo file CSV đơn hàng cần đặt cho tuần tới
        
        Logic ưu tiên:
        1. Đảm bảo đủ lượng tồn kho tối thiểu (Tồn nhỏ nhất)
        2. Sản phẩm bán được nhiều ưu tiên cao hơn
        3. Sản phẩm tạo nhiều doanh thu được highlight (vàng - high margin)
        
        Args:
            forecasts: DataFrame dự báo (nếu None sẽ chạy predict)
            top_n: Số sản phẩm cần đặt
            output_path: Đường dẫn file output
            lead_time_max: Lead time tối đa (ngày) - mặc định 7
            lead_time_avg: Lead time trung bình (ngày) - mặc định 5
        
        Công thức: Lượng cần nhập = MAX(Dự báo 7 ngày, Tồn nhỏ nhất) - Tồn kho hiện tại
        
        Args:
            forecasts: DataFrame từ predict_next_week(). Nếu None sẽ chạy dự báo mới.
            top_n: Số sản phẩm cần đặt (mặc định 50)
            output_path: Đường dẫn file output. Nếu None sẽ dùng mặc định.
            
        Returns:
            Đường dẫn file CSV đã tạo
        """
        logger.info("=" * 60)
        logger.info("📦 TẠO ĐƠN HÀNG CẦN ĐẶT (Purchase Order)")
        logger.info("=" * 60)
        
        # Nếu không có forecasts thì chạy dự báo mới
        if forecasts is None or forecasts.empty:
            logger.info("Chưa có dữ liệu dự báo, đang chạy predict_next_week...")
            forecasts = self.predict_next_week(use_abc_filter=True, abc_top_n=50)
        
        if forecasts.empty:
            logger.error("❌ Không có dữ liệu dự báo để tạo đơn hàng")
            return None
        
        product_list = forecasts['ma_hang'].unique().tolist()
        products_str = "', '".join(str(p) for p in product_list)
        
        # 1. Lấy thông tin từ PostgreSQL (mã vạch, tồn nhỏ nhất)
        logger.info("📥 Đang lấy thông tin tồn kho tối thiểu từ DanhSachSanPham...")
        try:
            from sqlalchemy import text
            with self.pg.get_connection() as conn:
                product_info_query = f"""
                SELECT 
                    ma_hang,
                    ma_vach,
                    ten_hang,
                    thuong_hieu,
                    gia_von_mac_dinh,
                    gia_ban_mac_dinh,
                    COALESCE(ton_nho_nhat, 0) as ton_nho_nhat
                FROM products
                WHERE ma_hang IN ('{products_str}')
                """
                product_info_df = pd.read_sql(text(product_info_query), conn)
                product_info = {}
                for _, row in product_info_df.iterrows():
                    product_info[row['ma_hang']] = {
                        'ma_vach': row['ma_vach'] or row['ma_hang'],
                        'ten_hang': row['ten_hang'],
                        'thuong_hieu': row['thuong_hieu'],
                        'gia_von': row['gia_von_mac_dinh'] or 0,
                        'gia_ban': row['gia_ban_mac_dinh'] or 0,
                        'ton_nho_nhat': row['ton_nho_nhat'] or 0,
                        'margin': ((row['gia_ban_mac_dinh'] - row['gia_von_mac_dinh']) / row['gia_von_mac_dinh'] * 100) 
                                  if row['gia_von_mac_dinh'] and row['gia_von_mac_dinh'] > 0 else 0
                    }
                logger.info(f"✅ Loaded {len(product_info)} products from DanhSachSanPham")
        except Exception as e:
            logger.warning(f"⚠️ Không thể load từ PostgreSQL: {e}")
            product_info = {}
        
        # 2. Lấy tồn kho HIỆN TẠI từ inventory_transactions (PostgreSQL)
        logger.info("📥 Đang lấy tồn kho hiện tại...")
        try:
            from sqlalchemy import text
            with self.pg.get_connection() as conn:
                inventory_query = f"""
                SELECT DISTINCT ON (ma_hang)
                    ma_hang,
                    ton_cuoi_ky as ton_hien_tai
                FROM inventory_transactions
                WHERE ma_hang IN ('{products_str}')
                ORDER BY ma_hang, ngay_bao_cao DESC
                """
                inventory_df = pd.read_sql(text(inventory_query), conn)
                current_stock_map = dict(zip(inventory_df['ma_hang'], inventory_df['ton_hien_tai']))
                logger.info(f"✅ Loaded current stock for {len(current_stock_map)} products")
        except Exception as e:
            logger.warning(f"⚠️ Không thể load tồn kho hiện tại: {e}")
            current_stock_map = {}
        
        # 3. Lấy số lượng bán THEO TUẦN (4 tuần gần nhất) để tính tồn kho tối ưu
        logger.info("📊 Đang tính tồn kho tối ưu từ dữ liệu 4 tuần...")
        try:
            # Query dữ liệu bán theo tuần
            weekly_sales_query = f"""
            SELECT 
                product_code as ma_hang,
                toWeek(transaction_date) as week_num,
                SUM(quantity_sold) as weekly_sold,
                SUM(gross_revenue) as weekly_revenue
            FROM retail_dw.fct_regular_sales
            WHERE product_code IN ('{products_str}')
              AND transaction_date >= today() - 28
            GROUP BY product_code, toWeek(transaction_date)
            ORDER BY product_code, week_num
            """
            weekly_df = self.ch.query(weekly_sales_query)
            
            # Tính tồn kho tối ưu cho mỗi sản phẩm
            # Công thức: tồn kho tối ưu = median(lượng bán tuần + tồn kho nhỏ nhất × 0.75) qua 4 tuần
            optimal_inventory_map = {}
            sales_map = {}
            
            for ma_hang in product_list:
                # Lấy dữ liệu 4 tuần của sản phẩm này
                product_weekly = weekly_df[weekly_df['ma_hang'] == ma_hang]
                
                if len(product_weekly) > 0:
                    # Lấy tồn kho nhỏ nhất từ database
                    ton_nho_nhat = product_info.get(ma_hang, {}).get('ton_nho_nhat', 0)
                    
                    # Tính tồn kho tối ưu cho mỗi tuần = bán tuần đó + tồn kho nhỏ nhất × 0.75
                    weekly_optimal = []
                    for _, week_row in product_weekly.iterrows():
                        weekly_sold = week_row['weekly_sold'] or 0
                        optimal_week = weekly_sold + (ton_nho_nhat * 0.75)
                        weekly_optimal.append(optimal_week)
                    
                    # Lấy trung vị (median) của 4 tuần
                    import numpy as np
                    optimal_inventory = np.median(weekly_optimal) if weekly_optimal else 0
                    
                    optimal_inventory_map[ma_hang] = round(optimal_inventory)
                    
                    # Lưu thêm tổng doanh thu 4 tuần cho ưu tiên
                    sales_map[ma_hang] = {
                        'quantity_sold': product_weekly['weekly_sold'].sum() or 0,
                        'revenue': product_weekly['weekly_revenue'].sum() or 0,
                        'weekly_data': weekly_optimal
                    }
                else:
                    optimal_inventory_map[ma_hang] = 0
                    sales_map[ma_hang] = {'quantity_sold': 0, 'revenue': 0, 'weekly_data': []}
            
            logger.info(f"✅ Calculated optimal inventory for {len(optimal_inventory_map)} products")
            logger.info(f"   Formula: median(weekly_sales + ton_nho_nhat × 0.75) over 4 weeks")
        except Exception as e:
            logger.warning(f"⚠️ Không thể tính tồn kho tối ưu: {e}")
            optimal_inventory_map = {}
            sales_map = {}
        
        # 3b. TÍNH TỒN KHO AN TOÀN (Safety Stock)
        logger.info("📊 Đang tính tồn kho an toàn (Safety Stock)...")
        logger.info(f"   Công thức: (Nhu cầu cao nhất × Lead time max) - (Nhu cầu TB × Lead time TB)")
        logger.info(f"   Lead time max: {lead_time_max} ngày, Lead time TB: {lead_time_avg} ngày")
        
        try:
            # Query dữ liệu bán theo NGÀY (28 ngày gần nhất) để tính nhu cầu
            daily_sales_query = f"""
            SELECT 
                product_code as ma_hang,
                transaction_date as ngay,
                SUM(quantity_sold) as daily_sold
            FROM retail_dw.fct_regular_sales
            WHERE product_code IN ('{products_str}')
              AND transaction_date >= today() - 28
            GROUP BY product_code, transaction_date
            ORDER BY product_code, transaction_date
            """
            daily_df = self.ch.query(daily_sales_query)
            
            # Tính Safety Stock cho mỗi sản phẩm
            safety_stock_map = {}
            
            for ma_hang in product_list:
                # Lấy dữ liệu bán hàng theo ngày của sản phẩm
                product_daily = daily_df[daily_df['ma_hang'] == ma_hang]
                
                if len(product_daily) >= 7:  # Cần ít nhất 7 ngày dữ liệu
                    daily_sold_list = product_daily['daily_sold'].tolist()
                    
                    # Tính nhu cầu cao nhất (max daily demand)
                    max_daily_demand = max(daily_sold_list)
                    
                    # Tính nhu cầu trung bình (average daily demand)
                    avg_daily_demand = sum(daily_sold_list) / len(daily_sold_list)
                    
                    # Công thức Safety Stock:
                    # (Nhu cầu cao nhất × Lead time max) - (Nhu cầu TB × Lead time TB)
                    safety_stock = (max_daily_demand * lead_time_max) - (avg_daily_demand * lead_time_avg)
                    safety_stock = max(0, round(safety_stock))  # Không âm
                    
                    safety_stock_map[ma_hang] = safety_stock
                else:
                    # Không đủ dữ liệu, dùng tồn nhỏ nhất làm safety stock
                    ton_nho_nhat = product_info.get(ma_hang, {}).get('ton_nho_nhat', 0)
                    safety_stock_map[ma_hang] = round(ton_nho_nhat * 0.5)  # 50% tồn nhỏ nhất
            
            logger.info(f"✅ Calculated Safety Stock for {len(safety_stock_map)} products")
        except Exception as e:
            logger.warning(f"⚠️ Không thể tính Safety Stock: {e}")
            safety_stock_map = {}
        
        # 4. Tổng hợp dự báo theo sản phẩm (7 ngày)
        product_summary = forecasts.groupby(['ma_hang', 'ten_san_pham']).agg({
            'predicted_quantity': 'sum'
        }).reset_index()
        product_summary.columns = ['ma_hang', 'ten_san_pham', 'forecast_7d']
        
        # 5. Thêm các thông tin bổ sung
        product_summary['ma_vach'] = product_summary['ma_hang'].map(
            lambda x: product_info.get(x, {}).get('ma_vach', x))
        product_summary['ten_hang_day_du'] = product_summary['ma_hang'].map(
            lambda x: product_info.get(x, {}).get('ten_hang', ''))
        product_summary['ton_nho_nhat'] = product_summary['ma_hang'].map(
            lambda x: product_info.get(x, {}).get('ton_nho_nhat', 0))
        product_summary['ton_hien_tai'] = product_summary['ma_hang'].map(
            lambda x: current_stock_map.get(x, 0))
        product_summary['ton_kho_toi_uu'] = product_summary['ma_hang'].map(
            lambda x: optimal_inventory_map.get(x, 0))  # Tồn kho tối ưu mới
        product_summary['ton_an_toan'] = product_summary['ma_hang'].map(
            lambda x: safety_stock_map.get(x, 0))  # Tồn kho an toàn (Safety Stock)
        product_summary['da_ban_4tuan'] = product_summary['ma_hang'].map(
            lambda x: sales_map.get(x, {}).get('quantity_sold', 0))
        product_summary['doanh_thu_4tuan'] = product_summary['ma_hang'].map(
            lambda x: sales_map.get(x, {}).get('revenue', 0))
        product_summary['margin_pct'] = product_summary['ma_hang'].map(
            lambda x: product_info.get(x, {}).get('margin', 0))
        
        # 6. Tính LƯỢNG CẦN NHẬP
        # Công thức mới: MAX(Dự báo 7 ngày, Tồn kho tối ưu + Tồn kho an toàn) - Tồn kho hiện tại
        # Trong đó: 
        # - Tồn kho tối ưu = median(lượng bán tuần + tồn kho nhỏ nhất × 0.75) qua 4 tuần
        # - Tồn kho an toàn = (Nhu cầu max × Lead time max) - (Nhu cầu TB × Lead time TB)
        product_summary['tong_ton_kho_muc_tieu'] = (
            product_summary['ton_kho_toi_uu'] + product_summary['ton_an_toan']
        )
        product_summary['luong_can_nhap'] = (
            product_summary[['forecast_7d', 'tong_ton_kho_muc_tieu']].max(axis=1) 
            - product_summary['ton_hien_tai']
        ).clip(lower=0)  # Không nhập số âm
        
        # 7. SẮP XẾP ƯU TIÊN
        # Primary: Lượng cần nhập (nhiều nhất = cần gấp nhất)
        # Secondary: Số lượng đã bán (bán nhiều = ưu tiên cao)
        # Tertiary: Doanh thu (để highlight high value)
        product_summary = product_summary.sort_values(
            ['luong_can_nhap', 'da_ban_4tuan', 'doanh_thu_4tuan'], 
            ascending=[False, False, False]
        )
        
        # 8. Lấy top N sản phẩm
        top_products = product_summary.head(top_n).copy()
        
        # Đánh dấu sản phẩm HIGH MARGIN (> 20% margin) và HIGH VALUE (top doanh thu)
        top_products['is_high_margin'] = top_products['margin_pct'] > 20
        top_products['is_high_value'] = top_products['doanh_thu_4tuan'] >= top_products['doanh_thu_4tuan'].quantile(0.8)
        
        logger.info(f"\n📊 Danh sách {len(top_products)} sản phẩm cần đặt hàng:")
        logger.info(f"   - Tổng lượng cần nhập: {top_products['luong_can_nhap'].sum():,.0f} units")
        logger.info(f"   - Tồn kho tối ưu TB: {top_products['ton_kho_toi_uu'].mean():,.0f} units")
        logger.info(f"   - Tồn kho an toàn TB: {top_products['ton_an_toan'].mean():,.0f} units")
        logger.info(f"   - Tổng mục tiêu TB: {top_products['tong_ton_kho_muc_tieu'].mean():,.0f} units")
        logger.info(f"   - Công thức Safety Stock: (Nhu cầu max × {lead_time_max}d) - (Nhu cầu TB × {lead_time_avg}d)")
        logger.info(f"   - Sản phẩm HIGH MARGIN (>20%): {top_products['is_high_margin'].sum()}")
        logger.info(f"   - Sản phẩm HIGH VALUE (top 20%): {top_products['is_high_value'].sum()}")
        
        # 9. Tạo đơn hàng
        purchase_orders = []
        for idx, row in top_products.iterrows():
            # Xác định mức độ ưu tiên
            if row['luong_can_nhap'] > row['ton_hien_tai'] * 2:
                uu_tien = '🔴 Cần gấp'
            elif row['luong_can_nhap'] > 0:
                uu_tien = '🟡 Cần đủ'
            else:
                uu_tien = '🟢 Đủ hàng'
            
            # Ghi chú highlight
            ghi_chu = ''
            if row['is_high_margin'] and row['is_high_value']:
                ghi_chu = '⭐ HIGH MARGIN + HIGH VALUE'
            elif row['is_high_margin']:
                ghi_chu = '💰 HIGH MARGIN'
            elif row['is_high_value']:
                ghi_chu = '💎 HIGH VALUE'
            
            purchase_orders.append({
                'stt': len(purchase_orders) + 1,
                'ma_hang': row['ma_hang'],
                'ma_vach': row['ma_vach'],
                'ten_san_pham': row['ten_hang_day_du'] or row['ten_san_pham'],
                'luong_can_nhap': round(row['luong_can_nhap']),
                'ton_kho_toi_uu': round(row['ton_kho_toi_uu']),  # Tồn kho tối ưu
                'ton_an_toan': round(row['ton_an_toan']),  # Tồn kho an toàn (Safety Stock)
                'tong_muc_tieu': round(row['tong_ton_kho_muc_tieu']),  # Tổng mục tiêu
                'ton_nho_nhat': round(row['ton_nho_nhat']),
                'ton_hien_tai': round(row['ton_hien_tai']),
                'du_bao_7ngay': round(row['forecast_7d']),
                'da_ban_4tuan': round(row['da_ban_4tuan']),
                'doanh_thu_4tuan': round(row['doanh_thu_4tuan']),
                'margin_pct': round(row['margin_pct'], 1),
                'uu_tien': uu_tien,
                'ghi_chu': ghi_chu
            })
        
        # 10. Tạo DataFrame và lưu file
        po_df = pd.DataFrame(purchase_orders)
        po_df['stt'] = range(1, len(po_df) + 1)
        
        if output_path is None:
            output_dir = '/app/output' if os.path.exists('/app/output') else os.getcwd()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = os.path.join(output_dir, f'purchase_order_{timestamp}.csv')
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        po_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        logger.info(f"\n✅ Đã tạo file đơn hàng: {output_path}")
        logger.info(f"   - Tổng lượng đặt: {po_df['luong_can_nhap'].sum():,.0f} units")
        
        # Hiển thị top 15
        logger.info("\n🔥 Top 15 sản phẩm ưu tiên đặt hàng:")
        logger.info(f"{'STT':<4} {'Mã hàng':<10} {'Tên sản phẩm':<26} {'Cần nhập':<9} {'Tối ưu':<8} {'An toàn':<8} {'Hiện tại':<9} {'Ưu tiên':<10}")
        logger.info("-" * 125)
        for _, row in po_df.head(15).iterrows():
            name_short = row['ten_san_pham'][:24] if len(str(row['ten_san_pham'])) > 24 else row['ten_san_pham']
            logger.info(f"{row['stt']:<4} {row['ma_hang']:<10} {name_short:<26} "
                       f"{row['luong_can_nhap']:>7,} {row['ton_kho_toi_uu']:>7,} {row['ton_an_toan']:>7,} {row['ton_hien_tai']:>7,} "
                       f"{row['uu_tien']:<10}")
        
        return output_path
    
    def generate_purchase_order_excel(self, forecasts: pd.DataFrame = None, 
                                       top_n: int = 50,
                                       output_path: str = None) -> str:
        """
        Tạo file Excel (.xlsx) đơn hàng cần đặt - Đơn giản hóa cho ngưởi dùng
        Chỉ gồm 3 cột: Tên sản phẩm, Mã vạch, Số lượng cần nhập
        
        Args:
            forecasts: DataFrame dự báo (nếu None sẽ chạy predict)
            top_n: Số sản phẩm cần đặt
            output_path: Đường dẫn file output
            
        Returns:
            Đường dẫn file Excel đã tạo
        """
        logger.info("=" * 60)
        logger.info("📦 TẠO FILE ĐƠN HÀNG EXCEL")
        logger.info("=" * 60)
        
        # Nếu không có forecasts thì chạy dự báo mới
        if forecasts is None or forecasts.empty:
            logger.info("Chưa có dữ liệu dự báo, đang chạy predict_next_week...")
            forecasts = self.predict_next_week(use_abc_filter=True, abc_top_n=top_n)
        
        if forecasts.empty:
            logger.error("❌ Không có dữ liệu dự báo để tạo đơn hàng")
            return None
        
        # Lấy danh sách sản phẩm và tổng số lượng cần nhập
        product_list = forecasts.groupby('ma_hang').agg({
            'predicted_quantity': 'sum',
            'ten_san_pham': 'first'
        }).sort_values('predicted_quantity', ascending=False).head(top_n)
        
        # Lấy mã vạch từ PostgreSQL
        try:
            from sqlalchemy import text
            ma_hang_list = product_list.index.tolist()
            ma_hang_str = "', '".join(str(m) for m in ma_hang_list)
            
            with self.pg.get_connection() as conn:
                query = f"""
                SELECT ma_hang, ma_vach, ten_hang
                FROM products
                WHERE ma_hang IN ('{ma_hang_str}')
                """
                product_info = pd.read_sql(text(query), conn)
                product_info = product_info.set_index('ma_hang')
        except Exception as e:
            logger.warning(f"⚠️ Không thể lấy mã vạch: {e}")
            product_info = pd.DataFrame()
        
        # Tạo DataFrame đơn giản với 3 cột
        simple_orders = []
        for ma_hang, row in product_list.iterrows():
            ten_sp = row['ten_san_pham'] if pd.notna(row['ten_san_pham']) else ''
            if not ten_sp and ma_hang in product_info.index:
                ten_sp = product_info.loc[ma_hang, 'ten_hang']
            
            ma_vach = ''
            if ma_hang in product_info.index:
                ma_vach = product_info.loc[ma_hang, 'ma_vach'] or ma_hang
            else:
                ma_vach = ma_hang
            
            simple_orders.append({
                'Tên sản phẩm': ten_sp,
                'Mã vạch': ma_vach,
                'Số lượng cần nhập': int(row['predicted_quantity'])
            })
        
        po_df = pd.DataFrame(simple_orders)
        
        # Tạo đường dẫn output
        if output_path is None:
            output_dir = '/app/output' if os.path.exists('/app/output') else os.getcwd()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = os.path.join(output_dir, f'don_hang_can_nhap_{timestamp}.xlsx')
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Lưu file Excel
        try:
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                po_df.to_excel(writer, index=False, sheet_name='Đơn hàng cần nhập')
                
                # Format cột
                workbook = writer.book
                worksheet = writer.sheets['Đơn hàng cần nhập']
                
                # Định dạng header
                for cell in worksheet[1]:
                    cell.font = workbook.create_font(bold=True)
                    cell.fill = workbook.create_fill(patternType='solid', fgColor='4472C4')
                    cell.font = workbook.create_font(bold=True, color='FFFFFF')
                
                # Auto adjust column width
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            logger.info(f"\n✅ Đã tạo file Excel đơn hàng: {output_path}")
            logger.info(f"   - Tổng số sản phẩm: {len(po_df)}")
            logger.info(f"   - Tổng số lượng cần nhập: {po_df['Số lượng cần nhập'].sum():,} units")
            
        except Exception as e:
            logger.error(f"❌ Lỗi khi tạo file Excel: {e}")
            # Fallback sang CSV nếu không có openpyxl
            csv_path = output_path.replace('.xlsx', '.csv')
            po_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            logger.info(f"✅ Đã tạo file CSV thay thế: {csv_path}")
            return csv_path
        
        return output_path
    
    def send_error_notification(self, error_message: str, context: str = ""):
        """Gửi thông báo lỗi qua email"""
        if self.email_notifier:
            try:
                self.email_notifier.send_error_alert(error_message, context)
            except Exception as e:
                logger.error(f"Không thể gửi email lỗi: {e}")

    def generate_comprehensive_report(self, days: int = 7) -> Dict:
        """
        Tạo báo cáo dự báo toàn diện từ cả 3 models
        
        Returns:
            Dict chứa các phần của báo cáo
        """
        import pandas as pd
        from datetime import datetime, timedelta
        
        logger.info("=" * 70)
        logger.info("📊 TẠO BÁO CÁO DỰ BÁO TOÀN DIỆN")
        logger.info("=" * 70)
        
        # Load models nếu chưa có
        if not self.models:
            for name in ['product_quantity', 'category_trend']:
                model_path = os.path.join(self.model_dir, f'{name}_model.pkl')
                if os.path.exists(model_path):
                    self.models[name] = joblib.load(model_path)
                    logger.info(f"✅ Loaded model: {name}")
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'forecast_period_days': days,
            'models_loaded': list(self.models.keys()),
            'sections': {}
        }
        
        # ========================================
        # PHẦN 1: DỰ BÁO SỐ LƯỢNG (Model 1)
        # ========================================
        logger.info("\n" + "-" * 50)
        logger.info("📦 PHẦN 1: DỰ BÁO SỐ LƯỢNG BÁN HÀNG (Model 1 - MdAPE)")
        logger.info("-" * 50)
        
        try:
            # Dự báo cho Top 50 sản phẩm cần nhập
            forecasts = self.predict_next_week(use_abc_filter=True, abc_top_n=50)
            
            if len(forecasts) > 0:
                # Tính tổng theo sản phẩm (dùng predicted_quantity)
                product_totals = forecasts.groupby('ma_hang').agg({
                    'predicted_quantity': 'sum',
                    'predicted_quantity_raw': 'sum',
                    'ten_san_pham': 'first',
                    'nhom_hang_cap_1': 'first',
                    'nhom_hang_cap_2': 'first',
                    'abc_class': 'first'
                }).sort_values('predicted_quantity', ascending=False)
                
                # Top 15 sản phẩm
                top_quantity = product_totals.head(15)
                
                logger.info(f"\n📊 TỔNG QUAN DỰ BÁO:")
                logger.info(f"   • Tổng số sản phẩm: {forecasts['ma_hang'].nunique()}")
                logger.info(f"   • Tổng số ngày dự báo: 7 ngày")
                logger.info(f"   • Tổng số lượng dự báo: {int(forecasts['predicted_quantity'].sum())} units")
                
                logger.info("\n🔥 Top 15 Sản phẩm dự báo bán chạy nhất (7 ngày tới):")
                for idx, (product, row) in enumerate(top_quantity.iterrows(), 1):
                    qty = row['predicted_quantity']
                    cat = row['nhom_hang_cap_1']
                    name = row.get('ten_san_pham', 'N/A')[:30]  # Giới hạn 30 ký tự
                    abc = row.get('abc_class', 'N/A')
                    logger.info(f"   {idx:2d}. {product} | {name:<30} | {qty:4d} units | {cat}")
                
                report['sections']['quantity_forecast'] = {
                    'total_products': forecasts['ma_hang'].nunique(),
                    'total_forecast_records': len(forecasts),
                    'total_predicted_quantity': int(forecasts['predicted_quantity'].sum()),
                    'total_predicted_quantity_raw': float(forecasts['predicted_quantity_raw'].sum()),
                    'top_15_products': top_quantity.reset_index().to_dict('records')
                }
            else:
                logger.warning("⚠️ Không có dữ liệu dự báo số lượng")
                report['sections']['quantity_forecast'] = {'error': 'No forecast data'}
                
        except Exception as e:
            logger.error(f"❌ Lỗi khi tạo dự báo số lượng: {e}")
            report['sections']['quantity_forecast'] = {'error': str(e)}
        
        # ========================================
        # PHẦN 2: XU HƯỚNG CATEGORY (Model 2)
        # ========================================
        logger.info("\n" + "-" * 50)
        logger.info("📊 PHẦN 2: XU HƯỚNG THEO CATEGORY (Model 2 - Category Trend Forecast)")
        logger.info("-" * 50)
        
        category_forecasts = pd.DataFrame()
        try:
            # Dự báo bằng Model 2 (Category-level)
            category_forecasts = self.predict_category_trend(days=days)
            
            if not category_forecasts.empty:
                # Tổng hợp theo category
                model2_by_category = category_forecasts.groupby('nhom_hang_cap_1').agg({
                    'predicted_quantity': 'sum',
                    'seasonal_factor': 'mean',
                    'is_peak_day': 'max'
                }).sort_values('predicted_quantity', ascending=False)
                
                logger.info("\n📈 Model 2 - Dự báo theo Category (7 ngày tới):")
                for cat, row in model2_by_category.head(10).iterrows():
                    qty = row['predicted_quantity']
                    sf = row['seasonal_factor']
                    logger.info(f"   • {cat}: {qty:5.0f} units (seasonal: {sf:.2f})")
                
                report['sections']['category_trend'] = {
                    'model2_by_category': model2_by_category.reset_index().to_dict('records'),
                    'total_categories': category_forecasts['nhom_hang_cap_1'].nunique(),
                    'total_forecast_records': len(category_forecasts),
                    'confidence': 'MEDIUM - Using dynamic seasonal factors'
                }
            else:
                logger.warning("⚠️ Model 2 không tạo được dự báo")
                report['sections']['category_trend'] = {'error': 'No category forecast generated'}
                
        except Exception as e:
            logger.error(f"❌ Lỗi khi chạy Model 2: {e}")
            report['sections']['category_trend'] = {'error': str(e)}
        
        # ========================================
        # PHẦN 3: VALIDATION - SO SÁNH VỚI DỮ LIỆU THỰC TẾ
        # ========================================
        logger.info("\n" + "-" * 50)
        logger.info("📊 PHẦN 3: VALIDATION - SO SÁNH DỰ BÁO VỚI THỰC TẾ (7 ngày)")
        logger.info("-" * 50)
        
        try:
            validation_results = self.validate_forecast_accuracy(days_back=7)
            report['sections']['validation'] = validation_results
        except Exception as e:
            logger.error(f"❌ Lỗi khi validation: {e}")
            report['sections']['validation'] = {'error': str(e)}
        
        # ========================================
        # PHẦN 4: SO SÁNH MODEL 1 vs MODEL 2
        # ========================================
        logger.info("\n" + "-" * 50)
        logger.info("📊 PHẦN 4: SO SÁNH MODEL 1 VS MODEL 2")
        logger.info("-" * 50)
        
        try:
            if not forecasts.empty and not category_forecasts.empty:
                comparison = self.compare_model_predictions(forecasts, category_forecasts)
                report['sections']['model_comparison'] = comparison
            else:
                logger.warning("⚠️ Thiếu dữ liệu để so sánh models")
                report['sections']['model_comparison'] = {'error': 'Insufficient data'}
        except Exception as e:
            logger.error(f"❌ Lỗi khi so sánh models: {e}")
            report['sections']['model_comparison'] = {'error': str(e)}
        
        # ========================================
        # PHẦN 5: KHUYẾN NGHỊ TỒN KHO
        # ========================================
        logger.info("\n" + "-" * 50)
        logger.info("📋 PHẦN 5: KHUYẾN NGHỊ TỒN KHO")
        logger.info("-" * 50)
        
        try:
            if len(forecasts) > 0:
                # Tính toán khuyến nghị cho top 10 sản phẩm có dự báo cao nhất
                top_products = forecasts.groupby('ma_hang').agg({
                    'predicted_quantity': 'sum',
                    'ten_san_pham': 'first',
                    'nhom_hang_cap_1': 'first'
                }).sort_values('predicted_quantity', ascending=False).head(10)
                
                recommendations = []
                logger.info("\n📦 Top 10 sản phẩm cần chú ý tồn kho:\n")
                
                for idx, (product, row) in enumerate(top_products.iterrows(), 1):
                    try:
                        qty = row['predicted_quantity']
                        cat = row['nhom_hang_cap_1']
                        name = row.get('ten_san_pham', 'N/A')[:30]  # Giới hạn 30 ký tự
                        
                        # Tính toán khuyến nghị đơn giản
                        avg_daily = qty / 7
                        safety_stock = round(avg_daily * 7 * 1.5)  # 1.5x weekly demand
                        reorder_point = round(avg_daily * 14)  # 2 weeks
                        suggested_order = round(avg_daily * 30)  # 1 month
                        urgency = 'HIGH' if qty > avg_daily * 14 else 'NORMAL'
                        
                        rec = {
                            'product_code': product,
                            'product_name': name,
                            'category': cat,
                            'predicted_7_days': int(qty),
                            'avg_daily_demand': round(avg_daily, 2),
                            'safety_stock': safety_stock,
                            'reorder_point': reorder_point,
                            'suggested_order_quantity': suggested_order,
                            'urgency': urgency
                        }
                        recommendations.append(rec)
                        
                        logger.info(f"   {idx:2d}. 📦 {product} | {name}")
                        logger.info(f"       ({cat}) | Dự báo: {qty:3.0f} units")
                        logger.info(f"       Safety stock: {safety_stock:3d} | Reorder point: {reorder_point:3d} | Mức độ ưu tiên: {urgency}")
                        
                    except Exception as e:
                        continue
                
                report['sections']['inventory_recommendations'] = recommendations
                logger.info(f"\n✅ Đã tạo {len(recommendations)} khuyến nghị tồn kho")
            else:
                logger.warning("⚠️ Không có dữ liệu để đưa ra khuyến nghị")
                
        except Exception as e:
            logger.error(f"❌ Lỗi khi tạo khuyến nghị tồn kho: {e}")
        
        # Lưu báo cáo
        report_path = os.path.join(self.model_dir, 'comprehensive_report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            # Chuyển đổi numpy types sang Python types
            import json
            def convert_to_serializable(obj):
                if hasattr(obj, 'item'):  # numpy type
                    return obj.item()
                elif isinstance(obj, dict):
                    return {k: convert_to_serializable(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_to_serializable(i) for i in obj]
                return obj
            
            json.dump(convert_to_serializable(report), f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"\n✅ Báo cáo đã được lưu tại: {report_path}")
        logger.info("=" * 70)
        
        # Gửi email báo cáo nếu có forecasts
        if 'forecasts' in locals() and len(forecasts) > 0 and self.email_notifier:
            try:
                logger.info("📧 Đang gửi email forecast report từ comprehensive report...")
                
                # THÊM DỮ LIỆU BÁN TUẦN TRƯỚC cho email report
                logger.info("📊 Query doanh số tuần trước cho email report...")
                try:
                    product_list = forecasts['ma_hang'].unique().tolist()
                    products_str = "', '".join(str(p) for p in product_list)
                    
                    # Lấy tuần mới nhất có dữ liệu để tính "tuần trước" chính xác
                    current_week_query = """
                    SELECT 
                        toWeek(MAX(transaction_date)) as current_week,
                        toYear(MAX(transaction_date)) as current_year
                    FROM retail_dw.fct_regular_sales
                    """
                    week_result = self.ch.query(current_week_query)
                    if week_result is not None and len(week_result) > 0 and week_result.iloc[0, 0] is not None:
                        current_week = int(week_result.iloc[0, 0])
                        current_year = int(week_result.iloc[0, 1])
                        # Tính tuần trước (xử lý chuyển năm)
                        if current_week == 1:
                            last_week = 52
                            last_year = current_year - 1
                        else:
                            last_week = current_week - 1
                            last_year = current_year
                        logger.info(f"   Tuần hiện tại: {current_year}-W{current_week:02d}, Tuần trước: {last_year}-W{last_week:02d}")
                    else:
                        last_week = "toWeek(today()) - 1"
                        last_year = "toYear(today())"
                        logger.warning("   Không lấy được tuần dữ liệu, dùng toWeek(today()) - 1")
                    
                    # Query theo tuần (từ thứ 2 đến chủ nhật tuần trước)
                    last_week_query = f"""
                    SELECT 
                        f.product_code as ma_hang,
                        SUM(f.quantity_sold) as last_week_sales,
                        SUM(f.gross_revenue) as last_week_revenue
                    FROM retail_dw.fct_regular_sales f
                    WHERE f.product_code IN ('{products_str}')
                      AND toYear(f.transaction_date) = {last_year}
                      AND toWeek(f.transaction_date) = {last_week}
                    GROUP BY f.product_code
                    """
                    last_week_df = self.ch.query(last_week_query)
                    
                    if not last_week_df.empty:
                        # Merge vào forecasts
                        forecasts = forecasts.merge(
                            last_week_df[['ma_hang', 'last_week_sales']], 
                            on='ma_hang', 
                            how='left'
                        )
                        forecasts['last_week_sales'] = forecasts['last_week_sales'].fillna(0)
                        total_last_week = forecasts['last_week_sales'].sum()
                        logger.info(f"✅ Đã thêm last_week_sales: {total_last_week:,.0f} units")
                    else:
                        logger.warning("⚠️ Không có dữ liệu bán tuần trước")
                        forecasts['last_week_sales'] = 0
                except Exception as e:
                    logger.warning(f"⚠️ Không thể lấy dữ liệu tuần trước: {e}")
                    forecasts['last_week_sales'] = 0
                
                # Lấy inventory recommendations từ report
                inventory_recs = report['sections'].get('inventory_recommendations', [])
                
                success = self.email_notifier.send_forecast_report(
                    forecasts=forecasts,
                    inventory_recommendations=inventory_recs,
                    model_dir=self.model_dir
                )
                
                if success:
                    logger.info("✅ Đã gửi email forecast report từ comprehensive report")
                else:
                    logger.warning("⚠️ Không thể gửi email forecast report")
            except Exception as e:
                logger.error(f"❌ Lỗi khi gửi email từ comprehensive report: {e}")
        
        return report


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='ML Forecasting Pipeline')
    parser.add_argument('--mode', choices=['train', 'predict', 'report', 'all'], 
                       default='all', help='Chế độ chạy')
    parser.add_argument('--trials', type=int, default=50,
                       help='Số lần thử nghiệm hyperparameter tuning')
    parser.add_argument('--days', type=int, default=0,
                       help='Số ngày dữ liệu lịch sử để train. 0 = load toàn bộ (default: 0)')
    parser.add_argument('--skip-if-no-new-data', action='store_true', default=True,
                       help='Skip training nếu không có dữ liệu mới (mặc định: True)')
    parser.add_argument('--force-train', action='store_true',
                       help='Buộc train lại dù không có dữ liệu mới')
    parser.add_argument('--min-new-days', type=int, default=1,
                       help='Số ngày dữ liệu mới tối thiểu để train lại')
    parser.add_argument('--deep', action='store_true',
                       help='Deep training mode: 150 trials, full features (chậm hơn nhưng chính xác hơn)')
    
    args = parser.parse_args()
    
    forecaster = SalesForecaster()
    
    if args.mode in ['train', 'all']:
        logger.info("🚀 Mode: TRAINING")
        
        # Deep training mode: tăng trials và đảm bảo đủ dữ liệu
        if args.deep:
            n_trials = 150
            logger.info("🔬 DEEP TRAINING MODE: 150 trials, extended features")
        else:
            n_trials = args.trials
            
        metrics = forecaster.train_all_models(
            n_trials=n_trials,
            days=args.days,
            send_email=True
        )
        logger.info(f"✅ Training completed with metrics: {list(metrics.keys())}")
    
    if args.mode in ['predict', 'all']:
        logger.info("🔮 Mode: PREDICTION")
        # Dự báo Top 50 sản phẩm cần nhập (theo doanh thu lịch sử)
        forecasts = forecaster.predict_next_week(use_abc_filter=True, abc_top_n=50)
        if len(forecasts) > 0:
            forecaster.save_forecasts(forecasts, send_email=True)
            logger.info(f"✅ Generated and saved {len(forecasts)} forecasts")
        else:
            logger.warning("⚠️ No forecasts generated")
    
    if args.mode in ['report', 'all']:
        logger.info("📊 Mode: COMPREHENSIVE REPORT")
        report = forecaster.generate_comprehensive_report()
        logger.info(f"✅ Report generated with sections: {list(report['sections'].keys())}")
