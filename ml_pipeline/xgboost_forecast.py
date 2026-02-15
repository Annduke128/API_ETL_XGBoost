"""
XGBoost Forecasting cho dự báo bán hàng và tồn kho
Sử dụng Optuna cho hyperparameter tuning
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import logging
import joblib
import os
import json
import warnings

import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, mean_absolute_percentage_error

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


class SalesForecaster:
    """Dự báo doanh số bán hàng sử dụng XGBoost"""
    
    def __init__(self, model_dir: str = '/app/models', enable_email: bool = True):
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)
        
        self.pg = PostgreSQLConnector(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            database=os.getenv('POSTGRES_DB', 'retail_db'),
            user=os.getenv('POSTGRES_USER', 'retail_user'),
            password=os.getenv('POSTGRES_PASSWORD', 'retail_password')
        )
        
        self.ch = ClickHouseConnector(
            host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
            database=os.getenv('CLICKHOUSE_DB', 'retail_dw'),
            user=os.getenv('CLICKHOUSE_USER', 'default'),
            password=os.getenv('CLICKHOUSE_PASSWORD', 'clickhouse_password')
        )
        
        self.models = {}
        self.metrics = {}
        self.studies = {}  # Lưu Optuna studies
        
        # Khởi tạo email notifier
        self.email_notifier = None
        if enable_email:
            try:
                self.email_notifier = get_notifier()
                logger.info("📧 Email notifier đã được khởi tạo")
            except Exception as e:
                logger.warning(f"⚠️ Không thể khởi tạo email notifier: {e}")
        self.feature_cols = []  # Sẽ được cập nhật động sau khi create_features
    
    def load_historical_data(self, days: int = 365) -> pd.DataFrame:
        """Load dữ liệu lịch sử từ ClickHouse"""
        query = f"""
        SELECT
            ngay,
            chi_nhanh,
            ma_hang,
            nhom_hang_cap_1,
            nhom_hang_cap_2,
            SUM(doanh_thu) as daily_revenue,
            SUM(so_luong) as daily_quantity,
            SUM(loi_nhuan_gop) as daily_profit,
            COUNT(DISTINCT ma_giao_dich) as transaction_count
        FROM retail_dw.fact_transactions
        WHERE ngay >= today() - {days}
        GROUP BY ngay, chi_nhanh, ma_hang, nhom_hang_cap_1, nhom_hang_cap_2
        ORDER BY ngay
        """
        
        df = self.ch.query(query)
        df['ngay'] = pd.to_datetime(df['ngay'])
        return df
    
    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Tạo features cho model"""
        df = df.copy()
        
        # Time-based features
        df['day_of_week'] = df['ngay'].dt.dayofweek
        df['day_of_month'] = df['ngay'].dt.day
        df['month'] = df['ngay'].dt.month
        df['week_of_year'] = df['ngay'].dt.isocalendar().week
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        df['is_month_start'] = df['ngay'].dt.is_month_start.astype(int)
        df['is_month_end'] = df['ngay'].dt.is_month_end.astype(int)
        
        # Vietnamese holidays (simplified)
        df['is_holiday'] = self._is_vietnamese_holiday(df['ngay']).astype(int)
        
        # Lag features - điều chỉnh dựa trên số ngày dữ liệu có sẵn
        df = df.sort_values(['chi_nhanh', 'ma_hang', 'ngay'])
        n_unique_days = df['ngay'].nunique()
        
        # Chỉ dùng các lag hợp lý dựa trên số ngày dữ liệu
        available_lags = [lag for lag in [1, 7, 14, 30] if lag < n_unique_days]
        if not available_lags:
            available_lags = [1]  # Ít nhất cần lag 1
        
        logger.info(f"Sử dụng lag features: {available_lags} (dữ liệu có {n_unique_days} ngày)")
        
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
        
        # Growth rate
        df['quantity_growth'] = df.groupby(['chi_nhanh', 'ma_hang'])['daily_quantity'].pct_change()
        
        # Encoding cho categorical
        df['branch_encoded'] = pd.Categorical(df['chi_nhanh']).codes
        df['category1_encoded'] = pd.Categorical(df['nhom_hang_cap_1']).codes
        df['category2_encoded'] = pd.Categorical(df['nhom_hang_cap_2']).codes
        
        return df
    
    def _is_vietnamese_holiday(self, dates: pd.Series) -> pd.Series:
        """Kiểm tra ngày lễ Việt Nam (simplified)"""
        holidays = []
        for date in dates:
            month_day = (date.month, date.day)
            # Tết (giả định)
            if date.month == 1 and date.day <= 5:
                holidays.append(True)
            # 30/4
            elif month_day == (4, 30):
                holidays.append(True)
            # 1/5
            elif month_day == (5, 1):
                holidays.append(True)
            # 2/9
            elif month_day == (9, 2):
                holidays.append(True)
            else:
                holidays.append(False)
        return pd.Series(holidays, index=dates.index)
    
    def train_model(self, df: pd.DataFrame, target_col: str = 'daily_quantity') -> xgb.XGBRegressor:
        """Train XGBoost model với default hyperparameters (không tuning)"""
        # Chỉ dropna trong target column, fillna cho features
        df_clean = df.dropna(subset=[target_col]).copy()
        
        # Kiểm tra dữ liệu
        if len(df_clean) == 0:
            logger.error(f"❌ Không có dữ liệu sau khi loại bỏ NA cho target '{target_col}'")
            return xgb.XGBRegressor(
                objective='reg:squarederror',
                n_estimators=100,
                max_depth=3,
                random_state=42
            )
        
        # Tự động xác định feature columns (bỏ qua các cột metadata và target)
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
        
        logger.info(f"📊 Sử dụng {len(available_features)} features: {available_features[:5]}...")
        
        X = df_clean[available_features].fillna(0)  # Fill NA với 0
        y = df_clean[target_col]
        
        # Điều chỉnh n_splits dựa trên số lượng dữ liệu
        n_splits = min(5, max(2, len(X) // 6))
        tscv = TimeSeriesSplit(n_splits=n_splits)
        
        # Default model
        model = xgb.XGBRegressor(
            objective='reg:squarederror',
            n_estimators=500,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1
        )
        
        # Train
        model.fit(X, y)
        
        # Cross-validation
        cv_scores = []
        for train_idx, val_idx in tscv.split(X):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
            
            model.fit(X_train, y_train)
            y_pred = model.predict(X_val)
            
            mape = mean_absolute_percentage_error(y_val, y_pred)
            cv_scores.append(mape)
        
        if cv_scores:
            logger.info(f"CV MAPE ({n_splits} folds): {np.mean(cv_scores):.4f} (+/- {np.std(cv_scores):.4f})")
        else:
            logger.warning("Không thể tính CV scores do thiếu dữ liệu")
        
        # Feature importance
        importance = pd.DataFrame({
            'feature': available_features,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)
        logger.info(f"Top 5 features: {importance.head().to_dict('records')}")
        
        return model

    def train_model_optuna(self, df: pd.DataFrame, target_col: str = 'daily_quantity', 
                          n_trials: int = 50, timeout: int = 600) -> xgb.XGBRegressor:
        """
        Train XGBoost với Bayesian Optimization sử dụng Optuna
        
        Args:
            df: DataFrame với features
            target_col: Cột target cần dự báo
            n_trials: Số lần thử hyperparameters
            timeout: Thờigian tối đa (giây)
        
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
        
        X = df_clean[available_features].fillna(0)
        y = df_clean[target_col]
        
        # Kiểm tra số lượng mẫu
        min_samples_required = 30  # Tối thiểu cho TimeSeriesSplit(n_splits=5)
        if len(X) < min_samples_required:
            logger.warning(f"⚠️ Ít dữ liệu ({len(X)} samples) cho target '{target_col}'. Sử dụng model mặc định.")
            return self.train_model(df_clean, target_col)
        
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
            logger.warning(f"⚠️ Không đủ dữ liệu cho CV. Chuyển sang train model đơn giản.")
            return self.train_model(df_clean, target_col)
        
        def objective(trial):
            """Objective function cho Optuna"""
            
            params = {
                'objective': 'reg:squarederror',
                'random_state': 42,
                'n_jobs': -1,
                'verbosity': 0,
                
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
                    early_stopping_rounds=30,
                    verbose=False
                )
                
                y_pred = model.predict(X_valid_cv)
                mape = mean_absolute_percentage_error(y_valid_cv, y_pred)
                cv_scores.append(mape)
            
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
        logger.info(f"✅ Best MAPE: {study.best_value:.4f}")
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
            early_stopping_rounds=50,
            verbose=False
        )
        
        # Validation metrics
        y_pred = final_model.predict(X_val)
        val_mape = mean_absolute_percentage_error(y_val, y_pred)
        val_rmse = np.sqrt(mean_squared_error(y_val, y_pred))
        val_mae = mean_absolute_error(y_val, y_pred)
        
        logger.info(f"📊 Validation MAPE: {val_mape:.4f}")
        logger.info(f"📊 Validation RMSE: {val_rmse:.4f}")
        logger.info(f"📊 Validation MAE: {val_mae:.4f}")
        
        # Feature importance
        importance = pd.DataFrame({
            'feature': available_features,
            'importance': final_model.feature_importances_
        }).sort_values('importance', ascending=False)
        logger.info(f"🏆 Top 5 features:\n{importance.head().to_string()}")
        
        # Lưu metrics và study
        self.metrics[target_col] = {
            'tuning_method': 'optuna',
            'best_params': study.best_params,
            'cv_mape': study.best_value,
            'val_mape': val_mape,
            'val_rmse': val_rmse,
            'val_mae': val_mae,
            'best_iteration': final_model.best_iteration,
            'n_trials': len(study.trials)
        }
        self.studies[target_col] = study
        
        # Lưu study
        study_path = os.path.join(self.model_dir, f'{target_col}_optuna_study.pkl')
        joblib.dump(study, study_path)
        logger.info(f"💾 Study saved to {study_path}")
        
        return final_model

    def train_model_random_search(self, df: pd.DataFrame, target_col: str = 'daily_quantity',
                                   n_iter: int = 20) -> xgb.XGBRegressor:
        """Fallback: RandomizedSearchCV khi Optuna không available"""
        
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
            n_jobs=-1
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
    
    def train_all_models(self, use_tuning: bool = True, tuning_method: str = 'optuna',
                         n_trials: int = 50, days: int = 365, send_email: bool = True) -> Dict:
        """
        Train models cho tất cả levels
        
        Args:
            use_tuning: Có sử dụng hyperparameter tuning không
            tuning_method: 'optuna' hoặc 'random_search'
            n_trials: Số lần thử nghiệm hyperparameters
            days: Số ngày dữ liệu lịch sử để train
            send_email: Có gửi email thông báo không
        
        Returns:
            Dict chứa metrics của tất cả models
        """
        import time
        start_time = time.time()
        
        logger.info("=" * 60)
        logger.info("🚀 BẮT ĐẦU TRAINING PIPELINE")
        logger.info("=" * 60)
        
        # Load data
        logger.info(f"📥 Loading {days} days of historical data...")
        df = self.load_historical_data(days=days)
        logger.info(f"✅ Loaded {len(df):,} rows")
        
        # Feature engineering
        logger.info("🔧 Creating features...")
        df_features = self.create_features(df)
        logger.info(f"✅ Created {len(self.feature_cols)} features")
        
        # Chọn training function
        if use_tuning:
            if tuning_method == 'optuna' and OPTUNA_AVAILABLE:
                train_func = lambda df, target: self.train_model_optuna(df, target, n_trials=n_trials)
                logger.info(f"🎯 Using Optuna tuning with {n_trials} trials")
            else:
                train_func = lambda df, target: self.train_model_random_search(df, target, n_iter=n_trials)
                logger.info(f"🎯 Using Random Search with {n_trials} iterations")
        else:
            train_func = self.train_model
            logger.info("⚡ Using default hyperparameters (no tuning)")
        
        # Model 1: Product-level quantity forecast
        logger.info("\n" + "-" * 40)
        logger.info("📦 Model 1: Product-Level Quantity Forecast")
        logger.info("-" * 40)
        self.models['product_quantity'] = train_func(df_features, 'daily_quantity')
        
        # Model 2: Revenue forecast
        logger.info("\n" + "-" * 40)
        logger.info("💰 Model 2: Revenue Forecast")
        logger.info("-" * 40)
        self.models['product_revenue'] = train_func(df_features, 'daily_revenue')
        
        # Model 3: Category-level
        logger.info("\n" + "-" * 40)
        logger.info("📊 Model 3: Category-Level Forecast")
        logger.info("-" * 40)
        category_df = df_features.groupby(['ngay', 'nhom_hang_cap_1']).agg({
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
        }).reset_index()
        
        # Tạo lại features cho category-level (không cần lag features phức tạp)
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
        
        # Encoding cho category
        category_df['category1_encoded'] = pd.Categorical(category_df['nhom_hang_cap_1']).codes
        
        # Thêm các cột cần thiết nhưng không có giá trị cho category-level
        category_df['chi_nhanh'] = 'ALL_BRANCHES'  # Dummy value
        category_df['ma_hang'] = 'ALL_PRODUCTS'    # Dummy value
        category_df['nhom_hang_cap_2'] = 'ALL_CAT2'  # Dummy value
        category_df['branch_encoded'] = 0
        category_df['category2_encoded'] = 0
        
        # Thêm các lag features còn thiếu với giá trị 0
        for col in self.feature_cols:
            if col not in category_df.columns:
                category_df[col] = 0
        
        self.models['category_quantity'] = train_func(category_df, 'daily_quantity')
        
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
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("📊 TRAINING SUMMARY")
        logger.info("=" * 60)
        for model_name, metrics in self.metrics.items():
            cv_mape = metrics.get('cv_mape', 'N/A')
            val_mape = metrics.get('val_mape', 'N/A')
            logger.info(f"📈 {model_name}:")
            logger.info(f"   CV MAPE: {cv_mape:.4f}" if isinstance(cv_mape, float) else f"   CV MAPE: {cv_mape}")
            if isinstance(val_mape, float):
                logger.info(f"   Val MAPE: {val_mape:.4f}")
        logger.info("=" * 60)
        
        # Gửi email thông báo
        training_duration = time.time() - start_time
        if send_email and self.email_notifier:
            try:
                logger.info("📧 Đang gửi email thông báo training...")
                success = self.email_notifier.send_training_report(
                    metrics=self.metrics,
                    training_duration=training_duration,
                    model_dir=self.model_dir
                )
                if success:
                    logger.info("✅ Đã gửi email training report thành công")
                else:
                    logger.warning("⚠️ Không thể gửi email training report")
            except Exception as e:
                logger.error(f"❌ Lỗi khi gửi email: {e}")
        
        return self.metrics

    def get_tuning_summary(self, target_col: str = None) -> pd.DataFrame:
        """Trả về summary của Optuna study"""
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
    
    def predict_next_week(self) -> pd.DataFrame:
        """Dự báo cho tuần tới"""
        # Load models nếu chưa có
        if not self.models:
            for name in ['product_quantity', 'product_revenue', 'category_quantity']:
                model_path = os.path.join(self.model_dir, f'{name}_model.pkl')
                if os.path.exists(model_path):
                    self.models[name] = joblib.load(model_path)
        
        # Tạo future dates
        future_dates = pd.date_range(
            start=datetime.now().date() + timedelta(days=1),
            periods=7,
            freq='D'
        )
        
        # Lấy danh sách sản phẩm
        products_query = """
        SELECT DISTINCT chi_nhanh, ma_hang, nhom_hang_cap_1, nhom_hang_cap_2
        FROM retail_dw.fact_transactions
        WHERE ngay >= today() - 30
        """
        products = self.ch.query(products_query)
        
        forecasts = []
        
        for date in future_dates:
            for _, product in products.iterrows():
                # Tạo features cho prediction
                features = pd.DataFrame({
                    'ngay': [date],
                    'chi_nhanh': [product['chi_nhanh']],
                    'ma_hang': [product['ma_hang']],
                    'nhom_hang_cap_1': [product['nhom_hang_cap_1']],
                    'nhom_hang_cap_2': [product['nhom_hang_cap_2']],
                    'daily_quantity': [0],
                    'daily_revenue': [0]
                })
                
                # Lấy lịch sử gần nhất cho lag features
                hist_query = f"""
                SELECT * FROM retail_dw.fact_transactions
                WHERE chi_nhanh = '{product['chi_nhanh']}'
                  AND ma_hang = '{product['ma_hang']}'
                  AND ngay >= today() - 35
                ORDER BY ngay DESC
                LIMIT 35
                """
                history = self.ch.query(hist_query)
                
                if len(history) > 0:
                    features = pd.concat([history, features], ignore_index=True)
                    features['ngay'] = pd.to_datetime(features['ngay'])
                    
                    features = self.create_features(features)
                    pred_features = features[features['ngay'] == date]
                    
                    if len(pred_features) > 0 and 'product_quantity' in self.models:
                        # Lấy feature names từ model đã train
                        model_features = self.models['product_quantity'].feature_names_in_
                        
                        # Tạo DataFrame với đúng features
                        X_pred = pd.DataFrame(0, index=[0], columns=model_features)
                        
                        # Fill giá trị từ pred_features nếu có
                        for col in model_features:
                            if col in pred_features.columns:
                                X_pred[col] = pred_features[col].fillna(0).values
                        
                        quantity_pred = self.models['product_quantity'].predict(X_pred)[0]
                        revenue_pred = self.models['product_revenue'].predict(X_pred)[0]
                        
                        forecasts.append({
                            'forecast_date': date,
                            'chi_nhanh': product['chi_nhanh'],
                            'ma_hang': product['ma_hang'],
                            'nhom_hang_cap_1': product['nhom_hang_cap_1'],
                            'predicted_quantity': max(0, round(quantity_pred)),
                            'predicted_revenue': max(0, revenue_pred),
                            'confidence_lower': max(0, quantity_pred * 0.8),
                            'confidence_upper': quantity_pred * 1.2,
                            'created_at': datetime.now()
                        })
        
        return pd.DataFrame(forecasts)
    
    def save_forecasts(self, forecasts: pd.DataFrame, send_email: bool = True):
        """Lưu dự báo vào database và gửi email thông báo"""
        # Tạo bảng nếu chưa có
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS ml_forecasts (
            id SERIAL PRIMARY KEY,
            forecast_date DATE NOT NULL,
            chi_nhanh VARCHAR(100),
            ma_hang VARCHAR(50),
            nhom_hang_cap_1 VARCHAR(200),
            predicted_quantity FLOAT,
            predicted_revenue DECIMAL(15,2),
            confidence_lower FLOAT,
            confidence_upper FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_forecasts_date ON ml_forecasts(forecast_date);
        CREATE INDEX IF NOT EXISTS idx_forecasts_product ON ml_forecasts(ma_hang);
        """
        
        from sqlalchemy import text
        with self.pg.get_connection() as conn:
            conn.execute(text(create_table_sql))
            
            # Insert forecasts
            forecasts.to_sql('ml_forecasts', conn, if_exists='append', index=False)
        
        logger.info(f"Saved {len(forecasts)} forecasts to database")
        
        # Gửi email thông báo kết quả dự báo
        if send_email and self.email_notifier and len(forecasts) > 0:
            try:
                logger.info("📧 Đang gửi email forecast report...")
                
                # Lấy một số khuyến nghị tồn kho cho top products
                inventory_recs = []
                if 'ma_hang' in forecasts.columns:
                    top_products = forecasts.groupby('ma_hang')['predicted_quantity'].sum().sort_values(ascending=False).head(10)
                    for product_code in top_products.index:
                        try:
                            rec = self.get_inventory_recommendations(product_code)
                            if 'error' not in rec:
                                inventory_recs.append(rec)
                        except:
                            pass
                
                success = self.email_notifier.send_forecast_report(
                    forecasts=forecasts,
                    inventory_recommendations=inventory_recs,
                    model_dir=self.model_dir
                )
                if success:
                    logger.info("✅ Đã gửi email forecast report thành công")
                else:
                    logger.warning("⚠️ Không thể gửi email forecast report")
            except Exception as e:
                logger.error(f"❌ Lỗi khi gửi email forecast: {e}")
    
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
    
    def send_error_notification(self, error_message: str, context: str = ""):
        """Gửi thông báo lỗi qua email"""
        if self.email_notifier:
            try:
                self.email_notifier.send_error_alert(error_message, context)
            except Exception as e:
                logger.error(f"Không thể gửi email lỗi: {e}")


if __name__ == '__main__':
    forecaster = SalesForecaster()
    
    # Train models
    metrics = forecaster.train_all_models()
    print(f"Training metrics: {metrics}")
    
    # Generate forecasts
    forecasts = forecaster.predict_next_week()
    forecaster.save_forecasts(forecasts)
    print(f"Generated {len(forecasts)} forecasts")
