#!/usr/bin/env python3
"""
Python UDFs cho Business Logic phức tạp
Chạy sau Spark ETL để xử lý các logic đặc thù
"""

import pandas as pd
import numpy as np
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Tuple
import json
import hashlib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ABCClassifier:
    """Phân loại ABC dựa trên doanh thu"""
    
    def classify(self, df: pd.DataFrame) -> pd.DataFrame:
        """Classify products into ABC categories"""
        # Group by product and calculate total revenue
        product_revenue = df.groupby(['ma_hang', 'ten_hang']).agg({
            'doanh_thu': 'sum',
            'so_luong': 'sum'
        }).reset_index()
        
        # Sort by revenue descending
        product_revenue = product_revenue.sort_values('doanh_thu', ascending=False)
        
        # Calculate cumulative percentage
        total_revenue = product_revenue['doanh_thu'].sum()
        product_revenue['revenue_pct'] = product_revenue['doanh_thu'] / total_revenue
        product_revenue['cumulative_pct'] = product_revenue['revenue_pct'].cumsum()
        
        # Assign ABC class
        product_revenue['abc_class'] = product_revenue['cumulative_pct'].apply(
            lambda x: 'A' if x <= 0.8 else ('B' if x <= 0.95 else 'C')
        )
        
        # Merge back to original dataframe
        df = df.merge(
            product_revenue[['ma_hang', 'abc_class', 'revenue_pct']],
            on='ma_hang',
            how='left'
        )
        
        return df


class SeasonalAnalyzer:
    """Phân tích tính mùa vụ của sản phẩm"""
    
    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add seasonal flags and patterns"""
        df = df.copy()
        
        # Ensure ngay is datetime
        df['ngay'] = pd.to_datetime(df['ngay'])
        
        # Add season
        df['season'] = df['ngay'].dt.month.apply(self._get_season)
        
        # Add day type (weekend/weekday)
        df['is_weekend'] = df['ngay'].dt.dayofweek.isin([5, 6])
        
        # Add month/quarter
        df['quarter'] = df['ngay'].dt.quarter
        df['month_name'] = df['ngay'].dt.strftime('%B')
        
        # Calculate seasonal index for each product
        seasonal_idx = self._calculate_seasonal_index(df)
        df = df.merge(seasonal_idx, on=['ma_hang', 'month'], how='left')
        
        return df
    
    def _get_season(self, month: int) -> str:
        if month in [12, 1, 2]:
            return 'Winter'
        elif month in [3, 4, 5]:
            return 'Spring'
        elif month in [6, 7, 8]:
            return 'Summer'
        else:
            return 'Autumn'
    
    def _calculate_seasonal_index(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate seasonal sales index for each product"""
        monthly_avg = df.groupby(['ma_hang', 'month']).agg({
            'doanh_thu': 'mean'
        }).reset_index()
        
        overall_avg = df.groupby('ma_hang')['doanh_thu'].mean().reset_index()
        overall_avg.columns = ['ma_hang', 'overall_avg_revenue']
        
        seasonal_idx = monthly_avg.merge(overall_avg, on='ma_hang')
        seasonal_idx['seasonal_index'] = (
            seasonal_idx['doanh_thu'] / seasonal_idx['overall_avg_revenue']
        )
        
        return seasonal_idx[['ma_hang', 'month', 'seasonal_index']]


class OutlierDetector:
    """Phát hiện outlier trong giao dịch"""
    
    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add outlier flags"""
        df = df.copy()
        
        # Z-score method for revenue
        df['revenue_zscore'] = np.abs(
            (df['doanh_thu'] - df['doanh_thu'].mean()) / df['doanh_thu'].std()
        )
        df['is_revenue_outlier'] = df['revenue_zscore'] > 3
        
        # IQR method for quantity
        Q1 = df['so_luong'].quantile(0.25)
        Q3 = df['so_luong'].quantile(0.75)
        IQR = Q3 - Q1
        df['is_quantity_outlier'] = (
            (df['so_luong'] < Q1 - 1.5 * IQR) | 
            (df['so_luong'] > Q3 + 1.5 * IQR)
        )
        
        # Margin outlier (negative or extremely high margin)
        df['is_margin_outlier'] = (
            (df['loi_nhuan_sp'] < 0) | 
            (df['ty_suat_loi_nhuan'] > 100)
        )
        
        return df


class BranchClassifier:
    """Phân loại chi nhánh theo peer group"""
    
    PEER_GROUPS = {
        'KPDT': 'UP',  # Khu phố đô thị
        'KCC': 'AP',   # Khu chung cư
        'KCN': 'IZ',   # Khu công nghiệp
        'CTT': 'TM',   # Chợ truyền thống
        'KVNT': 'RL'   # Khu vực nông thôn
    }
    
    def classify(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add branch peer group classification"""
        df = df.copy()
        
        # Extract peer group from chi_nhanh code
        df['peer_group'] = df['chi_nhanh'].apply(self._get_peer_group)
        
        # Calculate branch performance metrics
        branch_metrics = df.groupby('chi_nhanh').agg({
            'doanh_thu': ['sum', 'mean', 'count'],
            'loi_nhuan_gop': 'sum'
        }).reset_index()
        
        branch_metrics.columns = [
            'chi_nhanh', 'total_revenue', 'avg_transaction', 
            'transaction_count', 'total_profit'
        ]
        
        # Calculate branch rank within peer group
        branch_metrics['branch_rank'] = branch_metrics.groupby('peer_group')['total_revenue'].rank(ascending=False)
        
        # Merge back
        df = df.merge(
            branch_metrics[['chi_nhanh', 'peer_group', 'branch_rank']],
            on='chi_nhanh',
            how='left'
        )
        
        return df
    
    def _get_peer_group(self, branch_code: str) -> str:
        """Extract peer group from branch code"""
        for prefix, group in self.PEER_GROUPS.items():
            if branch_code.startswith(prefix):
                return group
        return 'OTHER'


class BusinessLogicProcessor:
    """Main processor combining all business logic"""
    
    def __init__(self):
        self.abc_classifier = ABCClassifier()
        self.seasonal_analyzer = SeasonalAnalyzer()
        self.outlier_detector = OutlierDetector()
        self.branch_classifier = BranchClassifier()
    
    def process(self, input_path: str, output_path: str) -> Dict:
        """Run full business logic pipeline"""
        logger.info("="*60)
        logger.info("Python UDFs - Business Logic Processing")
        logger.info("="*60)
        
        # Read intermediate data from Spark
        logger.info(f"Reading intermediate data from {input_path}")
        df = pd.read_parquet(input_path)
        logger.info(f"Loaded {len(df)} rows")
        
        # Apply business logic
        logger.info("Running ABC Classification...")
        df = self.abc_classifier.classify(df)
        
        logger.info("Running Seasonal Analysis...")
        df = self.seasonal_analyzer.analyze(df)
        
        logger.info("Running Outlier Detection...")
        df = self.outlier_detector.detect(df)
        
        logger.info("Running Branch Classification...")
        df = self.branch_classifier.classify(df)
        
        # Generate summary statistics
        stats = self._generate_stats(df)
        
        # Write final output
        logger.info(f"Writing final output to {output_path}")
        df.to_parquet(f"{output_path}/transactions_enriched.parquet", index=False)
        
        # Write stats
        with open(f"{output_path}/stats.json", 'w') as f:
            json.dump(stats, f, indent=2, default=str)
        
        logger.info("="*60)
        logger.info("Business Logic Processing Completed")
        logger.info("="*60)
        
        return stats
    
    def _generate_stats(self, df: pd.DataFrame) -> Dict:
        """Generate processing statistics"""
        return {
            'total_records': len(df),
            'abc_distribution': df['abc_class'].value_counts().to_dict(),
            'peer_group_distribution': df['peer_group'].value_counts().to_dict(),
            'outliers': {
                'revenue': int(df['is_revenue_outlier'].sum()),
                'quantity': int(df['is_quantity_outlier'].sum()),
                'margin': int(df['is_margin_outlier'].sum())
            },
            'seasonal_distribution': df['season'].value_counts().to_dict(),
            'date_range': {
                'min': str(df['ngay'].min()),
                'max': str(df['ngay'].max())
            },
            'processing_timestamp': datetime.now().isoformat()
        }


def main():
    parser = argparse.ArgumentParser(description='Business Logic Processor (Python UDFs)')
    parser.add_argument('--input', required=True, help='Input Parquet path from Spark')
    parser.add_argument('--output', required=True, help='Output path')
    parser.add_argument('--postgres-url', default='postgresql://postgres:5432/retail_db',
                        help='PostgreSQL URL')
    
    args = parser.parse_args()
    
    processor = BusinessLogicProcessor()
    stats = processor.process(args.input, args.output)
    
    logger.info(f"Processing stats: {json.dumps(stats, indent=2, default=str)}")


if __name__ == '__main__':
    main()
