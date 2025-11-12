#!/usr/bin/env python3
"""
Generate Evidently Report Comparing Models

Creates an Evidently report comparing predictions from different models
to evaluate their relative performance.
"""

import argparse
import logging
import pickle
import json
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np
import yaml
from evidently import Report
from evidently.presets import DataDriftPreset, DataSummaryPreset
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, confusion_matrix,
    precision_recall_curve, roc_curve
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config():
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def load_model_predictions(features_path: str, artifacts_dir: Path):
    """Load predictions from all trained models."""
    logger.info(f"Loading features from {features_path}...")
    df = pd.read_parquet(features_path)
    
    # Ensure timestamp is datetime
    if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Sort by timestamp
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # Load config
    config = load_config()
    threshold_percentile = config['model'].get('threshold_percentile', 95) / 100.0
    train_pct = 1 - config['model']['validation_split'] - (1 - config['model']['train_test_split'])
    val_pct = config['model']['validation_split']
    
    # Split data (same as training)
    n = len(df)
    n_train = int(n * train_pct)
    n_val = int(n * val_pct)
    
    df_train = df.iloc[:n_train].copy()
    df_val = df.iloc[n_train:n_train + n_val].copy()
    df_test = df.iloc[n_train + n_val:].copy()
    
    # Compute threshold
    tau = df_train['future_volatility'].quantile(threshold_percentile)
    
    # Create labels
    y_test = (df_test['future_volatility'] >= tau).astype(int)
    
    # Feature columns
    feature_cols = [
        'midprice_returns', 'bid_ask_spread', 'trade_intensity',
        'order_book_imbalance', 'rolling_std_returns',
        'rolling_mean_spread', 'rolling_mean_imbalance'
    ]
    available_features = [col for col in feature_cols if col in df.columns]
    
    X_test = df_test[available_features].fillna(0)
    
    predictions = {}
    
    # Load baseline predictions
    try:
        baseline_path = artifacts_dir / "baseline_params.json"
        if baseline_path.exists():
            with open(baseline_path, 'r') as f:
                baseline_params = json.load(f)
            
            mean_std = baseline_params['mean']
            std_std = baseline_params['std']
            zscore_threshold = baseline_params['threshold']
            
            # Compute baseline predictions
            z_scores = (X_test['rolling_std_returns'] - mean_std) / (std_std + 1e-8)
            baseline_proba = 1 / (1 + np.exp(-(z_scores - 2.0)))
            baseline_pred = (X_test['rolling_std_returns'] >= zscore_threshold).astype(int)
            
            predictions['baseline'] = {
                'predictions': baseline_pred,
                'probabilities': baseline_proba,
                'target': y_test
            }
            logger.info("✓ Loaded baseline predictions")
    except Exception as e:
        logger.warning(f"Could not load baseline predictions: {e}")
    
    # Load logistic regression predictions
    try:
        logistic_path = artifacts_dir / "logistic_model.pkl"
        threshold_path = artifacts_dir / "logistic_optimal_threshold.json"
        
        if logistic_path.exists():
            with open(logistic_path, 'rb') as f:
                logistic_model = pickle.load(f)
            
            logistic_proba = logistic_model.predict_proba(X_test)[:, 1]
            
            # Load optimal threshold
            threshold = 0.5
            if threshold_path.exists():
                with open(threshold_path, 'r') as f:
                    threshold_data = json.load(f)
                    threshold = threshold_data.get('optimal_threshold', 0.5)
            
            logistic_pred = (logistic_proba >= threshold).astype(int)
            
            predictions['logistic'] = {
                'predictions': logistic_pred,
                'probabilities': logistic_proba,
                'target': y_test
            }
            logger.info("✓ Loaded logistic regression predictions")
    except Exception as e:
        logger.warning(f"Could not load logistic predictions: {e}")
    
    # Load XGBoost predictions
    try:
        xgb_path = artifacts_dir / "xgb_model.pkl"
        threshold_path = artifacts_dir / "xgboost_optimal_threshold.json"
        
        if xgb_path.exists():
            with open(xgb_path, 'rb') as f:
                xgb_model = pickle.load(f)
            
            xgb_proba = xgb_model.predict_proba(X_test)[:, 1]
            
            # Load optimal threshold
            threshold = 0.5
            if threshold_path.exists():
                with open(threshold_path, 'r') as f:
                    threshold_data = json.load(f)
                    threshold = threshold_data.get('optimal_threshold', 0.5)
            
            xgb_pred = (xgb_proba >= threshold).astype(int)
            
            predictions['xgboost'] = {
                'predictions': xgb_pred,
                'probabilities': xgb_proba,
                'target': y_test
            }
            logger.info("✓ Loaded XGBoost predictions")
    except Exception as e:
        logger.warning(f"Could not load XGBoost predictions: {e}")
    
    # Load calibrated XGBoost predictions
    try:
        xgb_cal_path = artifacts_dir / "xgb_model_calibrated.pkl"
        threshold_path = artifacts_dir / "xgboost_calibrated_optimal_threshold.json"
        
        if xgb_cal_path.exists():
            with open(xgb_cal_path, 'rb') as f:
                xgb_cal_model = pickle.load(f)
            
            xgb_cal_proba = xgb_cal_model.predict_proba(X_test)[:, 1]
            
            # Load optimal threshold
            threshold = 0.5
            if threshold_path.exists():
                with open(threshold_path, 'r') as f:
                    threshold_data = json.load(f)
                    threshold = threshold_data.get('optimal_threshold', 0.5)
            
            xgb_cal_pred = (xgb_cal_proba >= threshold).astype(int)
            
            predictions['xgboost_calibrated'] = {
                'predictions': xgb_cal_pred,
                'probabilities': xgb_cal_proba,
                'target': y_test
            }
            logger.info("✓ Loaded calibrated XGBoost predictions")
    except Exception as e:
        logger.warning(f"Could not load calibrated XGBoost predictions: {e}")
    
    return predictions, df_test


def create_comparison_dataframes(predictions: dict):
    """Create DataFrames for Evidently comparison."""
    comparison_data = {}
    
    for model_name, pred_data in predictions.items():
        df = pd.DataFrame({
            'target': pred_data['target'],
            'prediction': pred_data['predictions'],
            'prediction_proba': pred_data['probabilities']
        })
        comparison_data[model_name] = df
    
    return comparison_data


def main():
    parser = argparse.ArgumentParser(description='Generate Evidently Model Comparison Report')
    parser.add_argument('--features', type=str, default='data/processed/features.parquet',
                       help='Path to features Parquet file')
    parser.add_argument('--output_dir', type=str, default='reports/evidently',
                       help='Output directory for reports')
    parser.add_argument('--artifacts_dir', type=str, default='models/artifacts',
                       help='Directory containing model artifacts')
    parser.add_argument('--reference_model', type=str, default='logistic',
                       choices=['baseline', 'logistic', 'xgboost', 'xgboost_calibrated'],
                       help='Reference model for comparison (default: logistic)')
    parser.add_argument('--config', type=str, default=None,
                       help='Path to config file')
    
    args = parser.parse_args()
    
    artifacts_dir = Path(args.artifacts_dir)
    
    # Load predictions
    predictions, df_test = load_model_predictions(args.features, artifacts_dir)
    
    if len(predictions) == 0:
        logger.error("No model predictions found! Please train models first.")
        return 1
    
    # Create comparison DataFrames
    comparison_data = create_comparison_dataframes(predictions)
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate comparison reports for each model vs reference
    reference_model = args.reference_model
    if reference_model not in comparison_data:
        # Use first available model as reference
        reference_model = list(comparison_data.keys())[0]
        logger.warning(f"Reference model '{args.reference_model}' not found, using '{reference_model}'")
    
    reference_data = comparison_data[reference_model]
    
    logger.info(f"\nGenerating model comparison reports (reference: {reference_model})...")
    
    # Generate data drift reports comparing predictions
    for model_name, current_data in comparison_data.items():
        if model_name == reference_model:
            continue
        
        logger.info(f"\nComparing {model_name} vs {reference_model}...")
        
        # Create DataFrames with predictions as features for drift analysis
        ref_df = pd.DataFrame({
            'prediction': reference_data['prediction'],
            'prediction_proba': reference_data['prediction_proba'],
            'target': reference_data['target']
        })
        curr_df = pd.DataFrame({
            'prediction': current_data['prediction'],
            'prediction_proba': current_data['prediction_proba'],
            'target': current_data['target']
        })
        
        # Generate data drift report
        drift_report = Report([DataDriftPreset()])
        drift_result = drift_report.run(
            reference_data=ref_df,
            current_data=curr_df
        )
        
        # Save report
        report_path = output_dir / f"model_comparison_{reference_model}_vs_{model_name}.html"
        drift_result.save_html(str(report_path))
        logger.info(f"✓ Saved comparison report to {report_path}")
    
    # Generate overall comparison report (all models)
    logger.info("\nGenerating overall model comparison report...")
    
    # Create a combined report comparing all models
    # Use XGBoost as reference if available, otherwise use first model
    if 'xgboost' in comparison_data:
        overall_reference = comparison_data['xgboost']
        ref_name = 'xgboost'
    else:
        overall_reference = list(comparison_data.values())[0]
        ref_name = list(comparison_data.keys())[0]
    
    # Create summary comparison
    summary_data = []
    for model_name, data in comparison_data.items():
        from sklearn.metrics import (
            precision_score, recall_score, f1_score, 
            roc_auc_score, average_precision_score, confusion_matrix
        )
        
        y_true = data['target']
        y_pred = data['prediction']
        y_proba = data['prediction_proba']
        
        try:
            roc_auc = roc_auc_score(y_true, y_proba) if len(set(y_true)) > 1 else np.nan
        except:
            roc_auc = np.nan
        
        try:
            pr_auc = average_precision_score(y_true, y_proba) if len(set(y_true)) > 1 else 0.0
        except:
            pr_auc = 0.0
        
        cm = confusion_matrix(y_true, y_pred)
        if cm.size == 4:
            tn, fp, fn, tp = cm.ravel()
        else:
            tn, fp, fn, tp = 0, 0, 0, 0
        
        summary_data.append({
            'model': model_name,
            'f1': f1_score(y_true, y_pred, zero_division=0),
            'precision': precision_score(y_true, y_pred, zero_division=0),
            'recall': recall_score(y_true, y_pred, zero_division=0),
            'roc_auc': roc_auc,
            'pr_auc': pr_auc,
            'tp': int(tp),
            'fp': int(fp),
            'tn': int(tn),
            'fn': int(fn)
        })
    
    summary_df = pd.DataFrame(summary_data)
    
    # Save summary
    summary_path = output_dir / "model_comparison_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    logger.info(f"✓ Saved comparison summary to {summary_path}")
    
    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("MODEL COMPARISON SUMMARY")
    logger.info("=" * 60)
    logger.info(f"\n{summary_df.to_string(index=False)}")
    
    logger.info(f"\nReports saved to: {output_dir}")
    logger.info(f"  - Comparison reports: model_comparison_*.html")
    logger.info(f"  - Summary: {summary_path}")
    
    return 0


if __name__ == "__main__":
    exit(main())

