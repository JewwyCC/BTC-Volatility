#!/usr/bin/env python3
"""
Model Inference Script

Loads trained models and performs inference on test data.
Measures latency to ensure < 2x real-time performance.
"""

import argparse
import logging
import time
import json
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
import numpy as np
import yaml
import mlflow
import mlflow.sklearn
from sklearn.linear_model import LogisticRegression
from dotenv import load_dotenv

# Try to import XGBoost
try:
    import xgboost as xgb
    import pickle
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

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


def load_baseline_model(artifacts_dir: Path) -> Dict:
    """Load baseline model parameters."""
    baseline_path = artifacts_dir / "baseline_params.json"
    if not baseline_path.exists():
        raise FileNotFoundError(f"Baseline parameters not found at {baseline_path}")
    
    with open(baseline_path, 'r') as f:
        params = json.load(f)
    
    logger.info(f"Loaded baseline model parameters: threshold={params['threshold']:.6f}")
    return params


def load_ml_model(artifacts_dir: Path, model_type: str = 'logistic'):
    """Load ML model from artifacts."""
    if model_type == 'xgboost' and XGBOOST_AVAILABLE:
        model_path = artifacts_dir / "xgb_model.pkl"
        if not model_path.exists():
            raise FileNotFoundError(f"XGBoost model not found at {model_path}")
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        logger.info(f"Loaded XGBoost model from {model_path}")
    else:
        model_path = artifacts_dir / "logistic_model.pkl"
        if not model_path.exists():
            raise FileNotFoundError(f"Logistic Regression model not found at {model_path}")
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        logger.info(f"Loaded Logistic Regression model from {model_path}")
    
    return model


def baseline_predict(X: pd.DataFrame, params: Dict) -> Tuple[np.ndarray, np.ndarray]:
    """Make predictions using baseline model."""
    # Z-score rule
    zscore_threshold = params['threshold']
    mean_std = params['mean']
    std_std = params['std']
    
    y_pred = (X['rolling_std_returns'] >= zscore_threshold).astype(int)
    y_pred_proba = np.clip((X['rolling_std_returns'] - mean_std) / (std_std + 1e-8), 0, 1)
    y_pred_proba = np.clip(y_pred_proba / 2.0, 0, 1)  # Normalize
    
    return y_pred, y_pred_proba


def ml_predict(model, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """Make predictions using ML model."""
    y_pred_proba = model.predict_proba(X)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)
    return y_pred, y_pred_proba


def measure_latency(predict_fn, X: pd.DataFrame, n_iterations: int = 100) -> Dict:
    """Measure inference latency."""
    # Warm-up
    _ = predict_fn(X.iloc[:10])
    
    # Measure latency
    times = []
    for _ in range(n_iterations):
        start = time.time()
        _ = predict_fn(X)
        elapsed = time.time() - start
        times.append(elapsed)
    
    times = np.array(times)
    
    return {
        'mean_latency_ms': np.mean(times) * 1000,
        'std_latency_ms': np.std(times) * 1000,
        'min_latency_ms': np.min(times) * 1000,
        'max_latency_ms': np.max(times) * 1000,
        'p95_latency_ms': np.percentile(times, 95) * 1000,
        'p99_latency_ms': np.percentile(times, 99) * 1000,
        'throughput_samples_per_sec': len(X) / np.mean(times)
    }


def main():
    parser = argparse.ArgumentParser(description='Run model inference')
    parser.add_argument('--features', type=str, default='data/processed/features.parquet',
                       help='Path to features Parquet file')
    parser.add_argument('--model_type', type=str, default='logistic',
                       choices=['baseline', 'logistic', 'xgboost'],
                       help='Model type to use')
    parser.add_argument('--artifacts_dir', type=str, default='models/artifacts',
                       help='Directory containing model artifacts')
    parser.add_argument('--output', type=str, default=None,
                       help='Output file for predictions (optional)')
    parser.add_argument('--test_latency', action='store_true',
                       help='Test inference latency')
    parser.add_argument('--config', type=str, default=None,
                       help='Path to config file')
    
    args = parser.parse_args()
    
    # Load configuration
    if args.config:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
    else:
        config = load_config()
    
    # Load features
    logger.info(f"Loading features from {args.features}...")
    df = pd.read_parquet(args.features)
    
    # Ensure timestamp is datetime
    if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Sort by timestamp and use test split
    df = df.sort_values('timestamp').reset_index(drop=True)
    test_pct = 1 - config['model']['train_test_split']
    n_test = int(len(df) * test_pct)
    df_test = df.iloc[-n_test:].copy()
    
    logger.info(f"Using {len(df_test)} test samples")
    
    # Feature columns
    feature_cols = [
        'midprice_returns', 'bid_ask_spread', 'trade_intensity',
        'order_book_imbalance', 'rolling_std_returns',
        'rolling_mean_spread', 'rolling_mean_imbalance'
    ]
    
    available_features = [col for col in feature_cols if col in df_test.columns]
    X_test = df_test[available_features].fillna(0)
    
    # Load model
    artifacts_dir = Path(args.artifacts_dir)
    
    if args.model_type == 'baseline':
        logger.info("Loading baseline model...")
        baseline_params = load_baseline_model(artifacts_dir)
        
        # Make predictions
        logger.info("Making predictions...")
        start_time = time.time()
        y_pred, y_pred_proba = baseline_predict(X_test, baseline_params)
        inference_time = time.time() - start_time
        
        model_name = "baseline_zscore"
    else:
        logger.info(f"Loading {args.model_type} model...")
        ml_model = load_ml_model(artifacts_dir, model_type=args.model_type)
        
        # Make predictions
        logger.info("Making predictions...")
        start_time = time.time()
        y_pred, y_pred_proba = ml_predict(ml_model, X_test)
        inference_time = time.time() - start_time
        
        model_name = f"ml_{args.model_type}"
    
    logger.info(f"Inference completed in {inference_time:.4f} seconds")
    logger.info(f"  Total samples: {len(X_test)}")
    logger.info(f"  Time per sample: {inference_time/len(X_test)*1000:.2f} ms")
    logger.info(f"  Throughput: {len(X_test)/inference_time:.1f} samples/sec")
    
    # Latency test
    if args.test_latency:
        logger.info("\nRunning latency test...")
        if args.model_type == 'baseline':
            def predict_fn(X):
                return baseline_predict(X, baseline_params)
        else:
            def predict_fn(X):
                return ml_predict(ml_model, X)
        
        latency_stats = measure_latency(predict_fn, X_test, n_iterations=100)
        
        logger.info("\nLatency Statistics:")
        logger.info(f"  Mean: {latency_stats['mean_latency_ms']:.2f} ms")
        logger.info(f"  Std: {latency_stats['std_latency_ms']:.2f} ms")
        logger.info(f"  Min: {latency_stats['min_latency_ms']:.2f} ms")
        logger.info(f"  Max: {latency_stats['max_latency_ms']:.2f} ms")
        logger.info(f"  P95: {latency_stats['p95_latency_ms']:.2f} ms")
        logger.info(f"  P99: {latency_stats['p99_latency_ms']:.2f} ms")
        logger.info(f"  Throughput: {latency_stats['throughput_samples_per_sec']:.1f} samples/sec")
        
        # Check if meets requirement (< 2x real-time for 60s window)
        window_size = config['features']['window_size']  # 60 seconds
        max_allowed_time = window_size * 2  # 120 seconds for all samples
        
        if inference_time < max_allowed_time:
            logger.info(f"✓ Latency requirement met: {inference_time:.2f}s < {max_allowed_time:.2f}s")
        else:
            logger.warning(f"⚠ Latency requirement not met: {inference_time:.2f}s >= {max_allowed_time:.2f}s")
    
    # Save predictions
    if args.output:
        output_path = Path(args.output)
        df_output = df_test[['timestamp', 'product_id']].copy()
        df_output['prediction'] = y_pred
        df_output['probability'] = y_pred_proba
        df_output.to_parquet(output_path, index=False)
        logger.info(f"✓ Predictions saved to {output_path}")
    else:
        # Save to default location
        output_dir = Path("reports")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"predictions_{model_name}.parquet"
        df_output = df_test[['timestamp', 'product_id']].copy()
        df_output['prediction'] = y_pred
        df_output['probability'] = y_pred_proba
        df_output.to_parquet(output_path, index=False)
        logger.info(f"✓ Predictions saved to {output_path}")
    
    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("INFERENCE SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Model: {model_name}")
    logger.info(f"Samples: {len(X_test)}")
    logger.info(f"Predictions - Spikes: {y_pred.sum()} ({y_pred.mean()*100:.2f}%)")
    logger.info(f"Predictions - Normal: {(1-y_pred).sum()} ({(1-y_pred.mean())*100:.2f}%)")
    logger.info(f"Mean probability: {y_pred_proba.mean():.4f}")
    logger.info(f"Std probability: {y_pred_proba.std():.4f}")
    
    return 0


if __name__ == "__main__":
    exit(main())

