#!/usr/bin/env python3
"""
Script chính để train XGBoost models với Optuna hyperparameter tuning
"""

import argparse
import logging
import sys
import traceback
from xgboost_forecast import SalesForecaster
from email_notifier import get_notifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Train XGBoost forecasting models với hyperparameter tuning'
    )
    parser.add_argument(
        '--no-tuning', 
        action='store_true',
        help='Train without hyperparameter tuning (nhanh hơn)'
    )
    parser.add_argument(
        '--method',
        type=str,
        default='optuna',
        choices=['optuna', 'random'],
        help='Phương pháp tuning (default: optuna)'
    )
    parser.add_argument(
        '--trials',
        type=int,
        default=50,
        help='Số lần thử nghiệm hyperparameters (default: 50)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=365,
        help='Số ngày dữ liệu lịch sử để train (default: 365)'
    )
    parser.add_argument(
        '--predict',
        action='store_true',
        help='Generate forecasts sau khi train'
    )
    parser.add_argument(
        '--no-email',
        action='store_true',
        help='Không gửi email thông báo'
    )
    
    args = parser.parse_args()
    
    # Initialize forecaster
    forecaster = SalesForecaster(enable_email=not args.no_email)
    
    try:
        # Train models
        logger.info("=" * 60)
        logger.info("🚀 XGBOOST FORECASTING TRAINING")
        logger.info("=" * 60)
        logger.info(f"Tuning: {'OFF' if args.no_tuning else 'ON'}")
        logger.info(f"Method: {args.method}")
        logger.info(f"Trials: {args.trials}")
        logger.info(f"Historical days: {args.days}")
        logger.info(f"Email notifications: {'OFF' if args.no_email else 'ON'}")
        logger.info("=" * 60)
        
        metrics = forecaster.train_all_models(
            use_tuning=not args.no_tuning,
            tuning_method=args.method,
            n_trials=args.trials,
            days=args.days,
            send_email=not args.no_email
        )
        
        # Generate forecasts nếu cần
        if args.predict:
            logger.info("\n🔮 Generating forecasts...")
            forecasts = forecaster.predict_next_week()
            forecaster.save_forecasts(forecasts, send_email=not args.no_email)
            logger.info(f"✅ Saved {len(forecasts)} forecasts")
        
        logger.info("\n✨ Training completed!")
        
    except Exception as e:
        error_msg = f"{str(e)}\n\n{traceback.format_exc()}"
        logger.error(f"❌ Training failed: {error_msg}")
        
        # Gửi email thông báo lỗi
        if not args.no_email:
            forecaster.send_error_notification(
                error_message=error_msg,
                context=f"Training với method={args.method}, trials={args.trials}, days={args.days}"
            )
        
        sys.exit(1)


if __name__ == '__main__':
    main()
