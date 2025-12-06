#!/usr/bin/env python3
"""Compare Solution 1 (lower threshold) vs Solution 2 (stratified split)."""

import yaml
import pandas as pd
from pathlib import Path


def analyze_solution(config_path: str, solution_name: str):
    """Analyze a solution configuration."""
    # Load config
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Load data
    df = pd.read_parquet("data/processed/features.parquet")
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Get config
    train_pct = (
        1
        - config["model"]["validation_split"]
        - (1 - config["model"]["train_test_split"])
    )
    val_pct = config["model"]["validation_split"]
    test_pct = 1 - config["model"]["train_test_split"]  # noqa: F841
    threshold_percentile = config["model"].get("threshold_percentile", 95) / 100.0
    split_strategy = config["model"].get("split_strategy", "temporal")

    # Temporal split
    n_train = int(len(df) * train_pct)
    n_val = int(len(df) * val_pct)

    df_train = df.iloc[:n_train].copy()
    df_val = df.iloc[n_train : n_train + n_val].copy()
    df_test = df.iloc[n_train + n_val :].copy()

    # Compute threshold
    tau = df_train["future_volatility"].quantile(threshold_percentile)

    # Create labels
    y_train = (df_train["future_volatility"] >= tau).astype(int)
    y_val = (df_val["future_volatility"] >= tau).astype(int)
    y_test = (df_test["future_volatility"] >= tau).astype(int)

    print(f"\n{'='*60}")
    print(f"SOLUTION: {solution_name}")
    print(f"{'='*60}")
    print(f"Threshold percentile: {threshold_percentile*100:.0f}%")
    print(f"Threshold (τ): {tau:.8f}")
    print(f"Split strategy: {split_strategy}")
    print("\nLabel distribution:")
    print(
        f"  Train - Positives: {y_train.sum()} ({y_train.mean()*100:.2f}%), Negatives: {(1-y_train).sum()} ({(1-y_train.mean())*100:.2f}%)"
    )
    print(
        f"  Validation - Positives: {y_val.sum()} ({y_val.mean()*100:.2f}%), Negatives: {(1-y_val).sum()} ({(1-y_val.mean())*100:.2f}%)"
    )
    print(
        f"  Test - Positives: {y_test.sum()} ({y_test.mean()*100:.2f}%), Negatives: {(1-y_test).sum()} ({(1-y_test.mean())*100:.2f}%)"
    )

    # Evaluation metrics
    has_val_pos = y_val.sum() > 0
    has_test_pos = y_test.sum() > 0

    print("\nEvaluation capability:")
    print(f"  Validation set can be evaluated: {has_val_pos}")
    print(f"  Test set can be evaluated: {has_test_pos}")

    if not has_val_pos:
        print("  ⚠️  WARNING: Validation set has no positives!")
    if not has_test_pos:
        print("  ⚠️  WARNING: Test set has no positives!")

    return {
        "solution": solution_name,
        "threshold_percentile": threshold_percentile * 100,
        "tau": tau,
        "train_positives": y_train.sum(),
        "train_pos_ratio": y_train.mean(),
        "val_positives": y_val.sum(),
        "val_pos_ratio": y_val.mean(),
        "test_positives": y_test.sum(),
        "test_pos_ratio": y_test.mean(),
        "can_eval_val": has_val_pos,
        "can_eval_test": has_test_pos,
    }


# Test Solution 1: Lower threshold (90th percentile, temporal split)
print("=" * 60)
print("COMPARING SOLUTIONS")
print("=" * 60)

# Solution 1a: 90th percentile, temporal split
config_90 = {
    "model": {
        "train_test_split": 0.8,
        "validation_split": 0.1,
        "random_seed": 42,
        "threshold_percentile": 90,
        "split_strategy": "temporal",
    }
}
config_path_90 = Path("config.yaml")
with open(config_path_90, "w") as f:
    yaml.dump(config_90, f)
result_90 = analyze_solution(
    "config.yaml", "Solution 1a: 90th percentile, temporal split"
)

# Solution 1b: 85th percentile, temporal split
config_85 = {
    "model": {
        "train_test_split": 0.8,
        "validation_split": 0.1,
        "random_seed": 42,
        "threshold_percentile": 85,
        "split_strategy": "temporal",
    }
}
with open(config_path_90, "w") as f:
    yaml.dump(config_85, f)
result_85 = analyze_solution(
    "config.yaml", "Solution 1b: 85th percentile, temporal split"
)

# Solution 2: 95th percentile, stratified temporal split
config_strat = {
    "model": {
        "train_test_split": 0.8,
        "validation_split": 0.1,
        "random_seed": 42,
        "threshold_percentile": 95,
        "split_strategy": "stratified_temporal",
        "min_positive_ratio": 0.01,
    }
}
with open(config_path_90, "w") as f:
    yaml.dump(config_strat, f)
result_strat = analyze_solution(
    "config.yaml", "Solution 2: 95th percentile, stratified temporal split"
)

# Summary comparison
print(f"\n{'='*60}")
print("SUMMARY COMPARISON")
print(f"{'='*60}")
print(f"\n{'Metric':<40} {'Sol 1a (90%)':<20} {'Sol 1b (85%)':<20} {'Sol 2 (Strat)'}")
print(f"{'-'*100}")
print(
    f"{'Threshold percentile':<40} {result_90['threshold_percentile']:<20.0f} {result_85['threshold_percentile']:<20.0f} {result_strat['threshold_percentile']:.0f}"
)
print(
    f"{'Train positives':<40} {result_90['train_positives']:<20} {result_85['train_positives']:<20} {result_strat['train_positives']}"
)
print(
    f"{'Validation positives':<40} {result_90['val_positives']:<20} {result_85['val_positives']:<20} {result_strat['val_positives']}"
)
print(
    f"{'Test positives':<40} {result_90['test_positives']:<20} {result_85['test_positives']:<20} {result_strat['test_positives']}"
)
print(
    f"{'Can evaluate validation':<40} {result_90['can_eval_val']:<20} {result_85['can_eval_val']:<20} {result_strat['can_eval_val']}"
)
print(
    f"{'Can evaluate test':<40} {result_90['can_eval_test']:<20} {result_85['can_eval_test']:<20} {result_strat['can_eval_test']}"
)

# Restore original config
config_original = {
    "model": {
        "train_test_split": 0.8,
        "validation_split": 0.1,
        "random_seed": 42,
        "threshold_percentile": 95,
        "split_strategy": "stratified_temporal",
        "min_positive_ratio": 0.01,
    }
}
with open(config_path_90, "w") as f:
    yaml.dump(config_original, f)
