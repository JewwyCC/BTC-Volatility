#!/usr/bin/env python3
"""
Model Training Script

Trains baseline (z-score rule) and ML models (Logistic Regression/XGBoost)
for volatility spike detection. Uses time-based train/validation/test splits
and logs everything to MLflow.
"""

import argparse
import logging
import warnings
from pathlib import Path

import pandas as pd
import numpy as np
import yaml
import mlflow
import mlflow.sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    precision_recall_curve,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    confusion_matrix,
)
from sklearn.exceptions import UndefinedMetricWarning
from dotenv import load_dotenv

# Try to import XGBoost, fall back to Logistic Regression if not available
try:
    import xgboost as xgb

    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logging.warning("XGBoost not available, will use Logistic Regression only")

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_config():
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def compute_threshold_from_training(
    df_train: pd.DataFrame, percentile: float = 0.95
) -> float:
    """Compute threshold (tau) as percentile of future volatility in training data."""
    tau = df_train["future_volatility"].quantile(percentile)
    logger.info(
        f"Computed threshold (τ) from training data: {tau:.8f} ({percentile*100:.0f}th percentile)"
    )
    return tau


def create_labels(df: pd.DataFrame, tau: float) -> pd.Series:
    """Create binary labels based on threshold."""
    return (df["future_volatility"] >= tau).astype(int)


def baseline_zscore_model(
    X: pd.DataFrame,
    y: pd.Series,
    threshold_std: float = 2.0,
    precomputed_params: dict = None,
) -> dict:
    """
    Baseline model: Z-score rule

    Predicts volatility spike if rolling_std_returns exceeds mean + threshold_std * std
    """
    if precomputed_params is None:
        # Compute z-score threshold on training data
        mean_std = X["rolling_std_returns"].mean()
        std_std = X["rolling_std_returns"].std()
        zscore_threshold = mean_std + threshold_std * std_std
    else:
        # Use precomputed parameters
        mean_std = precomputed_params["mean"]
        std_std = precomputed_params["std"]
        zscore_threshold = precomputed_params["threshold"]

    # Predictions
    y_pred = (X["rolling_std_returns"] >= zscore_threshold).astype(int)

    # Probabilities: normalize z-score to [0, 1] range
    z_scores = (X["rolling_std_returns"] - mean_std) / (std_std + 1e-8)
    # Map z-score to probability: z >= threshold_std -> prob >= 0.5
    y_pred_proba = 1 / (
        1 + np.exp(-(z_scores - threshold_std))
    )  # Sigmoid transformation

    return {
        "predictions": y_pred,
        "probabilities": y_pred_proba,
        "threshold": zscore_threshold,
        "mean": mean_std,
        "std": std_std,
    }


def train_ml_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    model_type: str = "logistic",
    use_calibration: bool = False,
) -> object:
    """
    Train ML model (Logistic Regression or XGBoost).

    Args:
        X_train: Training features
        y_train: Training labels
        model_type: 'logistic' or 'xgboost'
        use_calibration: If True, apply Platt scaling calibration

    Returns:
        Trained model (calibrated if use_calibration=True)
    """
    if model_type == "xgboost" and XGBOOST_AVAILABLE:
        logger.info("Training XGBoost model...")
        base_model = xgb.XGBClassifier(
            n_estimators=200,  # Increased from 100
            max_depth=6,  # Increased from 5
            learning_rate=0.05,  # Reduced from 0.1 for better generalization
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=3,  # Added for regularization
            gamma=0.1,  # Added for regularization
            random_state=42,
            eval_metric="logloss",
            scale_pos_weight=len(y_train[y_train == 0])
            / len(y_train[y_train == 1]),  # Handle imbalance
        )
    else:
        logger.info("Training Logistic Regression model...")
        base_model = LogisticRegression(
            max_iter=1000,
            random_state=42,
            class_weight="balanced",  # Handle class imbalance
        )

    # Fit base model
    base_model.fit(X_train, y_train)

    # Apply calibration if requested
    if use_calibration:
        logger.info("Applying Platt scaling calibration...")
        calibrated_model = CalibratedClassifierCV(
            base_model,
            method="sigmoid",  # Platt scaling
            cv=3,  # 3-fold cross-validation for calibration
        )
        calibrated_model.fit(X_train, y_train)
        return calibrated_model
    else:
        return base_model


def find_optimal_threshold(
    y_true: pd.Series, y_pred_proba: pd.Series, metric: str = "f1"
) -> float:
    """
    Find optimal threshold for binary classification.

    Args:
        y_true: True labels
        y_pred_proba: Predicted probabilities
        metric: Metric to optimize ('f1', 'f1_precision', 'f1_recall')

    Returns:
        Optimal threshold value
    """
    if len(set(y_true.unique())) < 2:
        # Only one class present, return default
        return 0.5

    precision, recall, thresholds = precision_recall_curve(y_true, y_pred_proba)

    if metric == "f1":
        # Maximize F1 score
        f1_scores = 2 * (precision * recall) / (precision + recall + 1e-8)
        optimal_idx = np.argmax(f1_scores)
    elif metric == "f1_precision":
        # Balance F1 with higher precision
        f1_scores = 2 * (precision * recall) / (precision + recall + 1e-8)
        # Weight by precision
        scores = f1_scores * (1 + precision)
        optimal_idx = np.argmax(scores)
    elif metric == "f1_recall":
        # Balance F1 with higher recall
        f1_scores = 2 * (precision * recall) / (precision + recall + 1e-8)
        # Weight by recall
        scores = f1_scores * (1 + recall)
        optimal_idx = np.argmax(scores)
    else:
        optimal_idx = len(thresholds) // 2

    if optimal_idx < len(thresholds):
        return thresholds[optimal_idx]
    else:
        return 0.5


def evaluate_model(
    y_true: pd.Series,
    y_pred: pd.Series,
    y_pred_proba: pd.Series,
    model_name: str,
    split_name: str,
) -> dict:
    """Compute evaluation metrics."""
    # Check if both classes are present
    unique_classes = set(y_true.unique())
    has_both_classes = len(unique_classes) == 2

    # Warn if no positive labels
    if 1 not in unique_classes:
        logger.warning(
            f"{model_name} - {split_name.upper()}: No positive labels (spikes) found. Metrics may be limited."
        )

    # Suppress sklearn warnings when only one class is present (we handle it explicitly)
    # Use context manager to suppress warnings for this evaluation
    with warnings.catch_warnings():
        if not has_both_classes:
            # Suppress all UndefinedMetricWarning and UserWarning from sklearn metrics
            warnings.filterwarnings("ignore", category=UndefinedMetricWarning)
            # Also suppress UserWarnings that sklearn emits for edge cases
            warnings.simplefilter("ignore", UserWarning)

        # PR-AUC (required) - returns 0.0 if no positive labels
        if has_both_classes:
            pr_auc = average_precision_score(y_true, y_pred_proba)
        else:
            pr_auc = 0.0

        # ROC-AUC - requires both classes
        if has_both_classes:
            try:
                roc_auc = roc_auc_score(y_true, y_pred_proba)
            except ValueError:
                roc_auc = np.nan
        else:
            roc_auc = np.nan

        # F1 score
        f1 = f1_score(y_true, y_pred, zero_division=0)

        # Precision and Recall
        precision = precision_score(y_true, y_pred, zero_division=0)
        recall = recall_score(y_true, y_pred, zero_division=0)

        # Confusion matrix - explicitly specify labels to ensure consistent shape
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        # cm is always 2x2 when labels=[0,1] is specified
        tn, fp, fn, tp = cm.ravel()

    metrics = {
        f"{split_name}_pr_auc": pr_auc,
        f"{split_name}_roc_auc": roc_auc,
        f"{split_name}_f1": f1,
        f"{split_name}_precision": precision,
        f"{split_name}_recall": recall,
        f"{split_name}_true_positives": int(tp),
        f"{split_name}_false_positives": int(fp),
        f"{split_name}_true_negatives": int(tn),
        f"{split_name}_false_negatives": int(fn),
    }

    logger.info(f"\n{model_name} - {split_name.upper()} Metrics:")
    logger.info(f"  PR-AUC: {pr_auc:.4f}")
    if np.isnan(roc_auc):
        logger.info("  ROC-AUC: nan (only one class present)")
    else:
        logger.info(f"  ROC-AUC: {roc_auc:.4f}")
    logger.info(f"  F1 Score: {f1:.4f}")
    logger.info(f"  Precision: {precision:.4f}")
    logger.info(f"  Recall: {recall:.4f}")
    logger.info(f"  Confusion Matrix: TP={tp}, FP={fp}, TN={tn}, FN={fn}")

    return metrics


def time_based_split(
    df: pd.DataFrame,
    train_pct: float = 0.7,
    val_pct: float = 0.1,
    test_pct: float = 0.2,
) -> tuple:
    """
    Split data based on time (not random).

    Returns: (train, val, test) DataFrames
    """
    # Ensure data is sorted by timestamp
    df = df.sort_values("timestamp").reset_index(drop=True)

    n = len(df)
    n_train = int(n * train_pct)
    n_val = int(n * val_pct)

    df_train = df.iloc[:n_train].copy()
    df_val = df.iloc[n_train : n_train + n_val].copy()
    df_test = df.iloc[n_train + n_val :].copy()

    logger.info("\nTime-based split:")
    logger.info(f"  Train: {len(df_train)} samples ({len(df_train)/n*100:.1f}%)")
    logger.info(f"    {df_train['timestamp'].min()} to {df_train['timestamp'].max()}")
    logger.info(f"  Validation: {len(df_val)} samples ({len(df_val)/n*100:.1f}%)")
    logger.info(f"    {df_val['timestamp'].min()} to {df_val['timestamp'].max()}")
    logger.info(f"  Test: {len(df_test)} samples ({len(df_test)/n*100:.1f}%)")
    logger.info(f"    {df_test['timestamp'].min()} to {df_test['timestamp'].max()}")

    return df_train, df_val, df_test


def stratified_temporal_split(
    df: pd.DataFrame,
    tau: float,
    train_pct: float = 0.7,
    val_pct: float = 0.1,
    test_pct: float = 0.2,
    min_positive_ratio: float = 0.01,
) -> tuple:
    """
    Split data based on time with stratification to ensure positives in all splits.

    Strategy:
    1. Do initial temporal split
    2. Create labels based on threshold
    3. If val/test have no positives, redistribute some from training
    4. Maintain approximate temporal order by swapping positives near split boundaries

    Returns: (train, val, test) DataFrames
    """
    # Ensure data is sorted by timestamp
    df = df.sort_values("timestamp").reset_index(drop=True).copy()

    # Create labels
    df["label"] = (df["future_volatility"] >= tau).astype(int)

    n = len(df)
    n_train = int(n * train_pct)
    n_val = int(n * val_pct)
    n_test = n - n_train - n_val

    # Initial temporal split
    df_train = df.iloc[:n_train].copy()
    df_val = df.iloc[n_train : n_train + n_val].copy()
    df_test = df.iloc[n_train + n_val :].copy()

    # Calculate target number of positives for each split
    total_positives = df["label"].sum()

    # Ensure minimum positive ratio in each split
    min_train_pos = max(1, int(n_train * min_positive_ratio))
    min_val_pos = max(1, int(n_val * min_positive_ratio))
    min_test_pos = max(1, int(n_test * min_positive_ratio))

    # Target: proportional distribution, but at least minimum
    target_train_pos = max(int(total_positives * train_pct), min_train_pos)
    target_val_pos = max(int(total_positives * val_pct), min_val_pos)
    target_test_pos = max(int(total_positives * test_pct), min_test_pos)

    # But don't exceed what's available
    max_available = total_positives
    if target_train_pos + target_val_pos + target_test_pos > max_available:
        # Scale down proportionally
        scale = max_available / (target_train_pos + target_val_pos + target_test_pos)
        target_train_pos = max(min_train_pos, int(target_train_pos * scale))
        target_val_pos = max(min_val_pos, int(target_val_pos * scale))
        target_test_pos = max(min_test_pos, int(target_test_pos * scale))

    # Get actual positives in each split
    train_positives = df_train[df_train["label"] == 1].copy()
    val_positives = df_val[df_val["label"] == 1].copy()
    test_positives = df_test[df_test["label"] == 1].copy()

    train_negatives = df_train[df_train["label"] == 0].copy()
    val_negatives = df_val[df_val["label"] == 0].copy()
    test_negatives = df_test[df_test["label"] == 0].copy()

    # Redistribute positives if needed
    # Strategy: Move positives from training to val/test, swapping with negatives
    # Prioritize positives closest to the split boundaries

    # For validation set
    if len(val_positives) < target_val_pos:
        needed = target_val_pos - len(val_positives)
        # Try to get positives from training first
        if len(train_positives) > target_train_pos:
            train_pos_sorted = train_positives.sort_values("timestamp", ascending=False)
            to_move = train_pos_sorted.head(min(needed, len(train_pos_sorted))).copy()

            val_neg_sorted = val_negatives.sort_values("timestamp", ascending=True)
            to_swap = val_neg_sorted.head(min(len(to_move), len(val_neg_sorted))).copy()

            train_positives = train_positives[
                ~train_positives.index.isin(to_move.index)
            ]
            val_positives = pd.concat([val_positives, to_move])
            val_negatives = val_negatives[~val_negatives.index.isin(to_swap.index)]
            train_negatives = pd.concat([train_negatives, to_swap])

            logger.info(
                f"  Swapped {len(to_move)} positives from train to val (maintaining temporal order)"
            )
        # If training doesn't have enough, try test set
        elif len(test_positives) > target_test_pos:
            test_pos_sorted = test_positives.sort_values("timestamp", ascending=True)
            to_move = test_pos_sorted.head(min(needed, len(test_pos_sorted))).copy()

            val_neg_sorted = val_negatives.sort_values("timestamp", ascending=True)
            to_swap = val_neg_sorted.head(min(len(to_move), len(val_neg_sorted))).copy()

            test_positives = test_positives[~test_positives.index.isin(to_move.index)]
            val_positives = pd.concat([val_positives, to_move])
            val_negatives = val_negatives[~val_negatives.index.isin(to_swap.index)]
            test_negatives = pd.concat([test_negatives, to_swap])

            logger.info(
                f"  Swapped {len(to_move)} positives from test to val (maintaining temporal order)"
            )

    # For test set
    if (
        len(test_positives) < target_test_pos
        and len(train_positives) > target_train_pos
    ):
        needed = target_test_pos - len(test_positives)
        # Get positives from training that are closest to test boundary
        train_pos_sorted = train_positives.sort_values("timestamp", ascending=False)
        to_move = train_pos_sorted.head(min(needed, len(train_pos_sorted))).copy()

        # Get negatives from test closest to training boundary
        test_neg_sorted = test_negatives.sort_values("timestamp", ascending=True)
        to_swap = test_neg_sorted.head(min(len(to_move), len(test_neg_sorted))).copy()

        # Swap
        train_positives = train_positives[~train_positives.index.isin(to_move.index)]
        test_positives = pd.concat([test_positives, to_move])
        test_negatives = test_negatives[~test_negatives.index.isin(to_swap.index)]
        train_negatives = pd.concat([train_negatives, to_swap])

        logger.info(
            f"  Swapped {len(to_move)} positives from train to test (maintaining temporal order)"
        )

    # Also check if we can redistribute from val to test if needed
    if len(test_positives) < target_test_pos and len(val_positives) > target_val_pos:
        needed = target_test_pos - len(test_positives)
        val_pos_sorted = val_positives.sort_values("timestamp", ascending=False)
        to_move = val_pos_sorted.head(min(needed, len(val_pos_sorted))).copy()

        test_neg_sorted = test_negatives.sort_values("timestamp", ascending=True)
        to_swap = test_neg_sorted.head(min(len(to_move), len(test_neg_sorted))).copy()

        val_positives = val_positives[~val_positives.index.isin(to_move.index)]
        test_positives = pd.concat([test_positives, to_move])
        test_negatives = test_negatives[~test_negatives.index.isin(to_swap.index)]
        val_negatives = pd.concat([val_negatives, to_swap])

        logger.info(
            f"  Swapped {len(to_move)} positives from val to test (maintaining temporal order)"
        )

    # Recombine splits
    df_train = (
        pd.concat([train_positives, train_negatives])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    df_val = (
        pd.concat([val_positives, val_negatives])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    df_test = (
        pd.concat([test_positives, test_negatives])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    # Drop label column (we'll recreate it later)
    df_train = df_train.drop(columns=["label"])
    df_val = df_val.drop(columns=["label"])
    df_test = df_test.drop(columns=["label"])

    logger.info("\nStratified temporal split:")
    logger.info(f"  Train: {len(df_train)} samples ({len(df_train)/n*100:.1f}%)")
    logger.info(f"    {df_train['timestamp'].min()} to {df_train['timestamp'].max()}")
    logger.info(f"  Validation: {len(df_val)} samples ({len(df_val)/n*100:.1f}%)")
    logger.info(f"    {df_val['timestamp'].min()} to {df_val['timestamp'].max()}")
    logger.info(f"  Test: {len(df_test)} samples ({len(df_test)/n*100:.1f}%)")
    logger.info(f"    {df_test['timestamp'].min()} to {df_test['timestamp'].max()}")

    return df_train, df_val, df_test


def main():
    parser = argparse.ArgumentParser(description="Train volatility detection models")
    parser.add_argument(
        "--features",
        type=str,
        default="data/processed/features.parquet",
        help="Path to features Parquet file",
    )
    parser.add_argument(
        "--mlflow_uri",
        type=str,
        default="http://localhost:5001",
        help="MLflow tracking URI",
    )
    parser.add_argument(
        "--experiment_name",
        type=str,
        default="volatility_detection",
        help="MLflow experiment name",
    )
    parser.add_argument(
        "--model_type",
        type=str,
        default="logistic",
        choices=["logistic", "xgboost"],
        help="ML model type",
    )
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Apply Platt scaling calibration to handle distribution shift",
    )
    parser.add_argument("--config", type=str, default=None, help="Path to config file")

    args = parser.parse_args()

    # Load configuration
    if args.config:
        with open(args.config, "r") as f:
            config = yaml.safe_load(f)
    else:
        config = load_config()

    # Load features
    logger.info(f"Loading features from {args.features}...")
    df = pd.read_parquet(args.features)

    # Ensure timestamp is datetime
    if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Sort by timestamp
    df = df.sort_values("timestamp").reset_index(drop=True)

    logger.info(f"Loaded {len(df)} feature rows")

    # Get configuration
    train_pct = (
        1
        - config["model"]["validation_split"]
        - (1 - config["model"]["train_test_split"])
    )
    val_pct = config["model"]["validation_split"]
    test_pct = 1 - config["model"]["train_test_split"]
    threshold_percentile = config["model"].get("threshold_percentile", 95) / 100.0
    split_strategy = config["model"].get("split_strategy", "temporal")
    min_positive_ratio = config["model"].get("min_positive_ratio", 0.01)

    # Split data based on strategy
    if split_strategy == "stratified_temporal":
        # For stratified split, we need tau first
        # Compute tau from initial temporal split of training data
        df_temp = df.sort_values("timestamp").reset_index(drop=True)
        n_train_temp = int(len(df_temp) * train_pct)
        df_train_temp = df_temp.iloc[:n_train_temp].copy()
        tau = compute_threshold_from_training(
            df_train_temp, percentile=threshold_percentile
        )

        # Now do stratified temporal split
        logger.info("\nUsing stratified temporal split strategy")
        df_train, df_val, df_test = stratified_temporal_split(
            df, tau, train_pct, val_pct, test_pct, min_positive_ratio
        )
    else:
        # Standard temporal split
        logger.info("\nUsing temporal split strategy")
        df_train, df_val, df_test = time_based_split(df, train_pct, val_pct, test_pct)

    # Compute threshold from training data (may have been redistributed)
    tau = compute_threshold_from_training(df_train, percentile=threshold_percentile)

    # Create labels
    y_train = create_labels(df_train, tau)
    y_val = create_labels(df_val, tau)
    y_test = create_labels(df_test, tau)

    logger.info("\nLabel distribution:")
    logger.info(
        f"  Train - Spikes (1): {y_train.sum()} ({y_train.mean()*100:.2f}%), Normal (0): {(1-y_train).sum()} ({(1-y_train.mean())*100:.2f}%)"
    )
    logger.info(
        f"  Validation - Spikes (1): {y_val.sum()} ({y_val.mean()*100:.2f}%), Normal (0): {(1-y_val).sum()} ({(1-y_val.mean())*100:.2f}%)"
    )
    logger.info(
        f"  Test - Spikes (1): {y_test.sum()} ({y_test.mean()*100:.2f}%), Normal (0): {(1-y_test).sum()} ({(1-y_test.mean())*100:.2f}%)"
    )

    # Warn if validation or test sets have no positive labels
    if y_val.sum() == 0:
        logger.warning(
            "WARNING: Validation set has no positive labels (spikes). Model evaluation will be limited."
        )
    if y_test.sum() == 0:
        logger.warning(
            "WARNING: Test set has no positive labels (spikes). Model evaluation will be limited."
        )

    # Feature columns
    feature_cols = [
        "midprice_returns",
        "bid_ask_spread",
        "trade_intensity",
        "order_book_imbalance",
        "rolling_std_returns",
        "rolling_mean_spread",
        "rolling_mean_imbalance",
    ]

    # Only include columns that exist
    available_features = [col for col in feature_cols if col in df.columns]

    X_train = df_train[available_features].fillna(0)
    X_val = df_val[available_features].fillna(0)
    X_test = df_test[available_features].fillna(0)

    # Set up MLflow (fail gracefully if MLflow is not available)
    try:
        mlflow.set_tracking_uri(args.mlflow_uri)
        mlflow.set_experiment(args.experiment_name)
        mlflow_available = True
    except Exception as e:
        logger.warning(f"Could not connect to MLflow at {args.mlflow_uri}: {e}")
        logger.warning("Continuing without MLflow logging...")
        mlflow_available = False

    # ===== BASELINE MODEL =====
    logger.info("\n" + "=" * 60)
    logger.info("TRAINING BASELINE MODEL (Z-Score Rule)")
    logger.info("=" * 60)

    # Create a context manager for MLflow (no-op if MLflow is not available)
    if mlflow_available:
        mlflow_context = mlflow.start_run(run_name="baseline_zscore")
    else:
        from contextlib import nullcontext

        mlflow_context = nullcontext()

    with mlflow_context:
        # Train baseline (compute parameters on training data)
        baseline_result = baseline_zscore_model(X_train, y_train, threshold_std=2.0)
        baseline_params = {
            "threshold": float(baseline_result["threshold"]),
            "mean": float(baseline_result["mean"]),
            "std": float(baseline_result["std"]),
        }

        # Evaluate on validation (use precomputed parameters)
        val_result = baseline_zscore_model(
            X_val, y_val, threshold_std=2.0, precomputed_params=baseline_params
        )
        y_val_pred_baseline = val_result["predictions"]
        y_val_proba_baseline = val_result["probabilities"]

        # Evaluate on test (use precomputed parameters)
        test_result = baseline_zscore_model(
            X_test, y_test, threshold_std=2.0, precomputed_params=baseline_params
        )
        y_test_pred_baseline = test_result["predictions"]
        y_test_proba_baseline = test_result["probabilities"]

        # Metrics
        metrics_val = evaluate_model(
            y_val, y_val_pred_baseline, y_val_proba_baseline, "Baseline", "val"
        )
        metrics_test = evaluate_model(
            y_test, y_test_pred_baseline, y_test_proba_baseline, "Baseline", "test"
        )

        # Log to MLflow (if available)
        if mlflow_available:
            try:
                mlflow.log_params(
                    {
                        "model_type": "baseline_zscore",
                        "threshold_std": 2.0,
                        "tau": tau,
                        "n_features": len(available_features),
                    }
                )
                mlflow.log_metrics({**metrics_val, **metrics_test})
            except Exception as e:
                logger.warning(f"Could not log to MLflow: {e}")

        # Save baseline parameters (include tau for reference)
        baseline_params_save = {
            "threshold": float(baseline_result["threshold"]),
            "mean": float(baseline_result["mean"]),
            "std": float(baseline_result["std"]),
            "tau": float(tau),
            "threshold_std": 2.0,
        }

        import json

        baseline_path = Path(__file__).parent / "artifacts" / "baseline_params.json"
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        with open(baseline_path, "w") as f:
            json.dump(baseline_params_save, f, indent=2)

        # Log artifact with relative path (if MLflow available)
        if mlflow_available:
            try:
                mlflow.log_artifact(str(baseline_path), artifact_path="artifacts")
            except Exception as e:
                logger.warning(f"Could not log artifact to MLflow: {e}")

        logger.info(f"Baseline parameters saved locally at {baseline_path}")
        if mlflow_available:
            logger.info("✓ Baseline model logged to MLflow")

    # ===== ML MODEL =====
    logger.info("\n" + "=" * 60)
    logger.info(f"TRAINING ML MODEL ({args.model_type.upper()})")
    logger.info("=" * 60)

    # Create a context manager for MLflow (no-op if MLflow is not available)
    if mlflow_available:
        mlflow_context = mlflow.start_run(run_name=f"ml_model_{args.model_type}")
    else:
        from contextlib import nullcontext

        mlflow_context = nullcontext()

    with mlflow_context:
        # Train ML model
        ml_model = train_ml_model(
            X_train, y_train, model_type=args.model_type, use_calibration=args.calibrate
        )

        # Get probabilities
        y_train_pred_proba = ml_model.predict_proba(X_train)[:, 1]
        y_val_pred_proba = ml_model.predict_proba(X_val)[:, 1]
        y_test_pred_proba = ml_model.predict_proba(X_test)[:, 1]

        # Find optimal threshold
        # Try validation set first, fall back to train if val has no positives
        # For imbalanced data with potential distribution shift, use a more conservative approach
        if y_val.sum() > 0:
            optimal_threshold = find_optimal_threshold(
                y_val, y_val_pred_proba, metric="f1"
            )
            logger.info(
                f"Optimal threshold (from validation set): {optimal_threshold:.4f}"
            )
        elif y_train.sum() > 0:
            # Use training set, but be aware of potential distribution shift
            # For imbalanced data, we want to balance precision and recall
            optimal_threshold = find_optimal_threshold(
                y_train, y_train_pred_proba, metric="f1"
            )
            logger.info(
                f"Optimal threshold (from training set, val has no positives): {optimal_threshold:.4f}"
            )
            logger.warning(
                "WARNING: Using training set for threshold selection. Test set may have different distribution."
            )

            # Also compute what the test-optimal threshold would be (for diagnostic purposes only)
            if y_test.sum() > 0:
                test_optimal_threshold = find_optimal_threshold(
                    y_test, y_test_pred_proba, metric="f1"
                )
                logger.info(
                    f"  (Diagnostic: Test-optimal threshold would be {test_optimal_threshold:.4f})"
                )
                logger.info(
                    f"  (Diagnostic: This suggests distribution shift - test has {y_test.mean()*100:.1f}% positives vs train {y_train.mean()*100:.1f}%)"
                )
        else:
            optimal_threshold = 0.5
            logger.warning(
                "No positive labels in train/val, using default threshold 0.5"
            )

        # Predictions with optimal threshold
        y_train_pred = (y_train_pred_proba >= optimal_threshold).astype(int)
        y_val_pred = (y_val_pred_proba >= optimal_threshold).astype(int)
        y_test_pred = (y_test_pred_proba >= optimal_threshold).astype(int)

        # Also evaluate at 0.5 threshold for comparison
        y_test_pred_05 = (y_test_pred_proba >= 0.5).astype(int)

        # Evaluate
        metrics_train = evaluate_model(
            y_train, y_train_pred, y_train_pred_proba, f"ML-{args.model_type}", "train"
        )
        metrics_val = evaluate_model(
            y_val, y_val_pred, y_val_pred_proba, f"ML-{args.model_type}", "val"
        )
        metrics_test = evaluate_model(
            y_test, y_test_pred, y_test_pred_proba, f"ML-{args.model_type}", "test"
        )

        # Also evaluate test at 0.5 threshold for comparison
        if y_test.sum() > 0:
            metrics_test_05 = evaluate_model(
                y_test,
                y_test_pred_05,
                y_test_pred_proba,
                f"ML-{args.model_type}",
                "test_05_threshold",
            )
            logger.info(
                f"\nComparison: Test set at 0.5 threshold vs optimal threshold ({optimal_threshold:.4f})"
            )
            logger.info(f"  F1 at 0.5: {metrics_test_05['test_05_threshold_f1']:.4f}")
            logger.info(f"  F1 at optimal: {metrics_test['test_f1']:.4f}")

        # Log to MLflow (if available)
        if mlflow_available:
            try:
                mlflow.log_params(
                    {
                        "model_type": args.model_type,
                        "tau": tau,
                        "n_features": len(available_features),
                        "features": ",".join(available_features),
                        "optimal_threshold": optimal_threshold,
                        "calibrated": args.calibrate,
                    }
                )

                if args.model_type == "xgboost" and XGBOOST_AVAILABLE:
                    mlflow.log_params(
                        {
                            "n_estimators": ml_model.n_estimators,
                            "max_depth": ml_model.max_depth,
                            "learning_rate": ml_model.learning_rate,
                        }
                    )

                mlflow.log_metrics({**metrics_train, **metrics_val, **metrics_test})
            except Exception as e:
                logger.warning(f"Could not log to MLflow: {e}")

        # Save model and threshold
        artifacts_dir = Path(__file__).parent / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Save optimal threshold
        model_suffix = f"{args.model_type}{'_calibrated' if args.calibrate else ''}"
        threshold_path = artifacts_dir / f"{model_suffix}_optimal_threshold.json"
        import json

        with open(threshold_path, "w") as f:
            json.dump(
                {"optimal_threshold": float(optimal_threshold), "tau": float(tau)},
                f,
                indent=2,
            )
        logger.info(f"Optimal threshold saved to {threshold_path}")

        # Log feature importance if available
        # Handle calibrated models (they wrap the base model)
        base_model = ml_model
        if hasattr(ml_model, "calibrated_classifiers_"):
            # For calibrated models, get the base estimator
            base_model = ml_model.calibrated_classifiers_[0].estimator

        if hasattr(base_model, "feature_importances_"):
            feature_importance = pd.DataFrame(
                {
                    "feature": available_features,
                    "importance": base_model.feature_importances_,
                }
            ).sort_values("importance", ascending=False)
            logger.info("\nFeature Importance:")
            for _, row in feature_importance.iterrows():
                logger.info(f"  {row['feature']}: {row['importance']:.6f}")
        elif hasattr(base_model, "coef_"):
            # For logistic regression, use absolute coefficients
            coef = base_model.coef_[0]
            feature_importance = pd.DataFrame(
                {
                    "feature": available_features,
                    "coefficient": coef,
                    "abs_coefficient": np.abs(coef),
                }
            ).sort_values("abs_coefficient", ascending=False)
            logger.info("\nFeature Importance (Logistic Regression Coefficients):")
            for _, row in feature_importance.iterrows():
                logger.info(
                    f"  {row['feature']}: {row['coefficient']:.6f} (abs: {row['abs_coefficient']:.6f})"
                )

        if args.model_type == "xgboost" and XGBOOST_AVAILABLE:
            model_filename = f"xgb_model{'_calibrated' if args.calibrate else ''}.pkl"
            model_path = artifacts_dir / model_filename
            import pickle

            with open(model_path, "wb") as f:
                pickle.dump(ml_model, f)
            # Try to log model to MLflow (if available)
            if mlflow_available:
                try:
                    mlflow.xgboost.log_model(ml_model, "model")
                except Exception as e:
                    logger.warning(f"Could not log XGBoost model to MLflow: {e}")
                    try:
                        mlflow.log_artifact(str(model_path), artifact_path="artifacts")
                    except Exception as e2:
                        logger.warning(f"Could not log model artifact: {e2}")
        else:
            model_filename = (
                f"logistic_model{'_calibrated' if args.calibrate else ''}.pkl"
            )
            model_path = artifacts_dir / model_filename
            import pickle

            with open(model_path, "wb") as f:
                pickle.dump(ml_model, f)
            # Try to log model to MLflow (if available)
            if mlflow_available:
                try:
                    mlflow.sklearn.log_model(ml_model, "model")
                except Exception as e:
                    logger.warning(f"Could not log sklearn model to MLflow: {e}")
                    try:
                        mlflow.log_artifact(str(model_path), artifact_path="artifacts")
                    except Exception as e2:
                        logger.warning(f"Could not log model artifact: {e2}")

        logger.info(f"✓ ML model saved to {model_path}")
        if mlflow_available:
            logger.info("✓ ML model logged to MLflow")

    logger.info("\n" + "=" * 60)
    logger.info("TRAINING COMPLETE")
    logger.info("=" * 60)
    if mlflow_available:
        logger.info(f"View results in MLflow UI: {args.mlflow_uri}")
        logger.info(f"Experiment: {args.experiment_name}")

    return 0


if __name__ == "__main__":
    exit(main())
