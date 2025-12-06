#!/usr/bin/env python3
"""
Diagnostic script to investigate model performance issues.
"""

import pandas as pd
import numpy as np
import pickle
from pathlib import Path
import yaml
from sklearn.metrics import precision_recall_curve, f1_score


def load_config():
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def main():
    # Load data
    df = pd.read_parquet("data/processed/features.parquet")
    print(f"Loaded {len(df)} feature rows")

    # Load config
    config = load_config()
    threshold_percentile = config["model"].get("threshold_percentile", 95) / 100.0
    train_pct = (
        1
        - config["model"]["validation_split"]
        - (1 - config["model"]["train_test_split"])
    )
    val_pct = config["model"]["validation_split"]
    1 - config["model"]["train_test_split"]

    # Sort by timestamp
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Split data (same as training)
    n = len(df)
    n_train = int(n * train_pct)
    n_val = int(n * val_pct)

    df_train = df.iloc[:n_train].copy()
    df_val = df.iloc[n_train : n_train + n_val].copy()
    df_test = df.iloc[n_train + n_val :].copy()

    # Compute threshold
    tau = df_train["future_volatility"].quantile(threshold_percentile)
    print(f"\nThreshold (τ): {tau:.8f} ({threshold_percentile*100:.0f}th percentile)")

    # Create labels
    y_train = (df_train["future_volatility"] >= tau).astype(int)
    y_val = (df_val["future_volatility"] >= tau).astype(int)
    y_test = (df_test["future_volatility"] >= tau).astype(int)

    print("\nLabel Distribution:")
    print(f"  Train - Positives: {y_train.sum()} ({y_train.mean()*100:.2f}%)")
    print(f"  Val - Positives: {y_val.sum()} ({y_val.mean()*100:.2f}%)")
    print(f"  Test - Positives: {y_test.sum()} ({y_test.mean()*100:.2f}%)")

    # Load model
    model_path = Path("models/artifacts/logistic_model.pkl")
    if not model_path.exists():
        print(f"\nERROR: Model not found at {model_path}")
        return

    with open(model_path, "rb") as f:
        model = pickle.load(f)

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
    available_features = [col for col in feature_cols if col in df.columns]

    X_train = df_train[available_features].fillna(0)
    X_val = df_val[available_features].fillna(0)
    X_test = df_test[available_features].fillna(0)

    # Get predictions
    y_train_proba = model.predict_proba(X_train)[:, 1]
    model.predict_proba(X_val)[:, 1]
    y_test_proba = model.predict_proba(X_test)[:, 1]

    print("\n=== PREDICTION PROBABILITY ANALYSIS ===")
    print("\nTrain set probabilities:")
    print(f"  Min: {y_train_proba.min():.4f}")
    print(f"  Max: {y_train_proba.max():.4f}")
    print(f"  Mean: {y_train_proba.mean():.4f}")
    print(f"  Median: {np.median(y_train_proba):.4f}")
    print(f"  Std: {y_train_proba.std():.4f}")
    print(
        f"  Predictions at 0.5 threshold: {(y_train_proba >= 0.5).sum()} / {len(y_train_proba)}"
    )

    print("\nTest set probabilities:")
    print(f"  Min: {y_test_proba.min():.4f}")
    print(f"  Max: {y_test_proba.max():.4f}")
    print(f"  Mean: {y_test_proba.mean():.4f}")
    print(f"  Median: {np.median(y_test_proba):.4f}")
    print(f"  Std: {y_test_proba.std():.4f}")
    print(
        f"  Predictions at 0.5 threshold: {(y_test_proba >= 0.5).sum()} / {len(y_test_proba)}"
    )

    # Check optimal threshold
    print("\n=== OPTIMAL THRESHOLD ANALYSIS ===")

    # For test set (if it has positives)
    if y_test.sum() > 0:
        precision, recall, thresholds = precision_recall_curve(y_test, y_test_proba)
        f1_scores = 2 * (precision * recall) / (precision + recall + 1e-8)
        optimal_idx = np.argmax(f1_scores)
        optimal_threshold = (
            thresholds[optimal_idx] if optimal_idx < len(thresholds) else 0.5
        )
        optimal_f1 = f1_scores[optimal_idx]

        print("\nTest set optimal threshold (F1-maximizing):")
        print(f"  Optimal threshold: {optimal_threshold:.4f}")
        print(f"  Optimal F1 score: {optimal_f1:.4f}")

        # Evaluate at optimal threshold
        y_test_pred_optimal = (y_test_proba >= optimal_threshold).astype(int)
        from sklearn.metrics import confusion_matrix

        cm = confusion_matrix(y_test, y_test_pred_optimal)
        tn, fp, fn, tp = cm.ravel()
        print(f"  Confusion Matrix: TP={tp}, FP={fp}, TN={tn}, FN={fn}")
        print(f"  Precision: {tp/(tp+fp) if (tp+fp) > 0 else 0:.4f}")
        print(f"  Recall: {tp/(tp+fn) if (tp+fn) > 0 else 0:.4f}")

        # Compare with 0.5 threshold
        y_test_pred_05 = (y_test_proba >= 0.5).astype(int)
        cm_05 = confusion_matrix(y_test, y_test_pred_05)
        tn_05, fp_05, fn_05, tp_05 = cm_05.ravel()
        print("\n  At 0.5 threshold:")
        print(f"    Confusion Matrix: TP={tp_05}, FP={fp_05}, TN={tn_05}, FN={fn_05}")
        print(f"    F1 Score: {f1_score(y_test, y_test_pred_05):.4f}")

    # Feature importance (for logistic regression, use coefficients)
    if hasattr(model, "coef_"):
        print("\n=== FEATURE IMPORTANCE (Logistic Regression Coefficients) ===")
        coef = model.coef_[0]
        feature_importance = pd.DataFrame(
            {
                "feature": available_features,
                "coefficient": coef,
                "abs_coefficient": np.abs(coef),
            }
        ).sort_values("abs_coefficient", ascending=False)
        print(feature_importance.to_string(index=False))

    # Data quality checks
    print("\n=== DATA QUALITY CHECKS ===")
    print("\nFeature statistics (test set):")
    print(X_test.describe())

    print("\nMissing values:")
    print(X_test.isnull().sum())

    print("\nFeature correlations with target (test set):")
    if y_test.sum() > 0:
        correlations = X_test.corrwith(y_test).sort_values(ascending=False)
        print(correlations)

    # Distribution shift analysis
    print("\n=== DISTRIBUTION SHIFT ANALYSIS ===")
    print("\nFeature means:")
    print(f"  Train: {X_train.mean().to_dict()}")
    print(f"  Test:  {X_test.mean().to_dict()}")

    print("\nFeature stds:")
    print(f"  Train: {X_train.std().to_dict()}")
    print(f"  Test:  {X_test.std().to_dict()}")


if __name__ == "__main__":
    main()
