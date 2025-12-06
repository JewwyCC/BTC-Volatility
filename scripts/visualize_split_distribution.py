#!/usr/bin/env python3
"""
Visualize the temporal distribution of volatility spikes across train/val/test splits.

This script shows:
1. How data is split temporally
2. Where volatility spikes occur in time
3. Why validation/test sets might have no spikes
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import yaml

# Set style
sns.set_style("whitegrid")
plt.rcParams["figure.figsize"] = (14, 8)


def load_config():
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def time_based_split(
    df: pd.DataFrame,
    train_pct: float = 0.7,
    val_pct: float = 0.1,
    test_pct: float = 0.2,
):
    """Split data based on time (not random)."""
    df = df.sort_values("timestamp").reset_index(drop=True)
    n = len(df)
    n_train = int(n * train_pct)
    n_val = int(n * val_pct)

    df_train = df.iloc[:n_train].copy()
    df_val = df.iloc[n_train : n_train + n_val].copy()
    df_test = df.iloc[n_train + n_val :].copy()

    return df_train, df_val, df_test


def main():
    # Load data
    features_path = Path(__file__).parent.parent / "data/processed/features.parquet"
    df = pd.read_parquet(features_path)

    # Ensure timestamp is datetime
    if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Sort by timestamp
    df = df.sort_values("timestamp").reset_index(drop=True)

    print("=" * 80)
    print("TEMPORAL DATA SPLIT ANALYSIS")
    print("=" * 80)
    print(f"\nTotal samples: {len(df)}")
    print(f"Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(
        f"Duration: {(df['timestamp'].max() - df['timestamp'].min()).total_seconds():.0f} seconds"
    )
    print(
        f"         = {(df['timestamp'].max() - df['timestamp'].min()).total_seconds() / 60:.1f} minutes"
    )

    # Load config
    config = load_config()
    train_pct = (
        1
        - config["model"]["validation_split"]
        - (1 - config["model"]["train_test_split"])
    )
    val_pct = config["model"]["validation_split"]
    test_pct = 1 - config["model"]["train_test_split"]
    threshold_percentile = config["model"].get("threshold_percentile", 95) / 100.0

    print("\nSplit configuration:")
    print(f"  Train: {train_pct*100:.1f}%")
    print(f"  Validation: {val_pct*100:.1f}%")
    print(f"  Test: {test_pct*100:.1f}%")
    print(f"  Threshold percentile: {threshold_percentile*100:.0f}th")

    # Split data
    df_train, df_val, df_test = time_based_split(df, train_pct, val_pct, test_pct)

    print("\nActual split sizes:")
    print(f"  Train: {len(df_train)} samples ({len(df_train)/len(df)*100:.1f}%)")
    print(f"    Time: {df_train['timestamp'].min()} to {df_train['timestamp'].max()}")
    print(f"  Validation: {len(df_val)} samples ({len(df_val)/len(df)*100:.1f}%)")
    print(f"    Time: {df_val['timestamp'].min()} to {df_val['timestamp'].max()}")
    print(f"  Test: {len(df_test)} samples ({len(df_test)/len(df)*100:.1f}%)")
    print(f"    Time: {df_test['timestamp'].min()} to {df_test['timestamp'].max()}")

    # Compute threshold from training data (as done in train.py)
    tau = df_train["future_volatility"].quantile(threshold_percentile)
    print("\nThreshold (τ) computed from training data:")
    print(f"  {threshold_percentile*100:.0f}th percentile: {tau:.8f}")

    # Create labels for each split using the training threshold
    y_train = (df_train["future_volatility"] >= tau).astype(int)
    y_val = (df_val["future_volatility"] >= tau).astype(int)
    y_test = (df_test["future_volatility"] >= tau).astype(int)

    print("\nLabel distribution (using training threshold):")
    print(
        f"  Train - Spikes (1): {y_train.sum()} ({y_train.mean()*100:.2f}%), Normal (0): {(1-y_train).sum()} ({(1-y_train.mean())*100:.2f}%)"
    )
    print(
        f"  Validation - Spikes (1): {y_val.sum()} ({y_val.mean()*100:.2f}%), Normal (0): {(1-y_val).sum()} ({(1-y_val.mean())*100:.2f}%)"
    )
    print(
        f"  Test - Spikes (1): {y_test.sum()} ({y_test.mean()*100:.2f}%), Normal (0): {(1-y_test).sum()} ({(1-y_test.mean())*100:.2f}%)"
    )

    # Analyze volatility distribution in each split
    print("\nVolatility statistics by split:")
    print(
        f"  Train - Mean: {df_train['future_volatility'].mean():.8f}, Std: {df_train['future_volatility'].std():.8f}, Max: {df_train['future_volatility'].max():.8f}"
    )
    print(
        f"  Validation - Mean: {df_val['future_volatility'].mean():.8f}, Std: {df_val['future_volatility'].std():.8f}, Max: {df_val['future_volatility'].max():.8f}"
    )
    print(
        f"  Test - Mean: {df_test['future_volatility'].mean():.8f}, Std: {df_test['future_volatility'].std():.8f}, Max: {df_test['future_volatility'].max():.8f}"
    )

    # Check if validation/test have spikes at all (using their own thresholds)
    tau_val = (
        df_val["future_volatility"].quantile(threshold_percentile)
        if len(df_val) > 0
        else np.nan
    )
    tau_test = (
        df_test["future_volatility"].quantile(threshold_percentile)
        if len(df_test) > 0
        else np.nan
    )

    print("\nIf we used each split's own threshold:")
    if not np.isnan(tau_val):
        print(
            f"  Validation {threshold_percentile*100:.0f}th percentile: {tau_val:.8f}"
        )
        print(
            f"    Spikes at this threshold: {(df_val['future_volatility'] >= tau_val).sum()}"
        )
    if not np.isnan(tau_test):
        print(f"  Test {threshold_percentile*100:.0f}th percentile: {tau_test:.8f}")
        print(
            f"    Spikes at this threshold: {(df_test['future_volatility'] >= tau_test).sum()}"
        )

    # Why no spikes in validation?
    print("\n" + "=" * 80)
    print("WHY NO SPIKES IN VALIDATION?")
    print("=" * 80)
    print(f"\nThe threshold τ = {tau:.8f} is computed from training data.")
    print(
        f"This threshold represents the {threshold_percentile*100:.0f}th percentile of training data's future_volatility."
    )
    print("\nValidation set statistics:")
    print(
        f"  Max future_volatility in validation: {df_val['future_volatility'].max():.8f}"
    )
    print(f"  Training threshold (τ): {tau:.8f}")
    if df_val["future_volatility"].max() < tau:
        print(
            "  → Validation's maximum volatility is LOWER than the training threshold!"
        )
        print("  → Therefore, NO samples in validation exceed the threshold.")
        print("  → This happens because volatility spikes are CLUSTERED in time.")
        print(
            "  → The validation period happened to be a 'calm' period with no spikes."
        )
    else:
        print(
            "  → Validation's maximum volatility exceeds the threshold, but no samples do."
        )
        print("  → This suggests the threshold is too high, or spikes are very rare.")

    # Create visualization
    fig, axes = plt.subplots(3, 1, figsize=(14, 10))

    # Plot 1: Temporal distribution of future_volatility
    ax1 = axes[0]
    ax1.scatter(
        df_train["timestamp"],
        df_train["future_volatility"],
        alpha=0.3,
        s=10,
        label="Train",
        color="blue",
    )
    ax1.scatter(
        df_val["timestamp"],
        df_val["future_volatility"],
        alpha=0.3,
        s=10,
        label="Validation",
        color="orange",
    )
    ax1.scatter(
        df_test["timestamp"],
        df_test["future_volatility"],
        alpha=0.3,
        s=10,
        label="Test",
        color="green",
    )
    ax1.axhline(
        tau, color="red", linestyle="--", linewidth=2, label=f"Threshold (τ={tau:.8f})"
    )
    ax1.set_xlabel("Timestamp")
    ax1.set_ylabel("Future Volatility")
    ax1.set_title("Temporal Distribution of Future Volatility Across Splits")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Add vertical lines for split boundaries
    ax1.axvline(
        df_train["timestamp"].max(),
        color="black",
        linestyle=":",
        linewidth=1,
        alpha=0.5,
    )
    ax1.axvline(
        df_val["timestamp"].max(), color="black", linestyle=":", linewidth=1, alpha=0.5
    )
    ax1.text(
        df_train["timestamp"].max(),
        ax1.get_ylim()[1] * 0.95,
        "Train/Val",
        rotation=90,
        va="top",
        ha="right",
        fontsize=8,
    )
    ax1.text(
        df_val["timestamp"].max(),
        ax1.get_ylim()[1] * 0.95,
        "Val/Test",
        rotation=90,
        va="top",
        ha="right",
        fontsize=8,
    )

    # Plot 2: Histogram of future_volatility by split
    ax2 = axes[1]
    ax2.hist(
        df_train["future_volatility"],
        bins=50,
        alpha=0.5,
        label="Train",
        color="blue",
        density=True,
    )
    ax2.hist(
        df_val["future_volatility"],
        bins=50,
        alpha=0.5,
        label="Validation",
        color="orange",
        density=True,
    )
    ax2.hist(
        df_test["future_volatility"],
        bins=50,
        alpha=0.5,
        label="Test",
        color="green",
        density=True,
    )
    ax2.axvline(
        tau, color="red", linestyle="--", linewidth=2, label=f"Threshold (τ={tau:.8f})"
    )
    ax2.set_xlabel("Future Volatility")
    ax2.set_ylabel("Density")
    ax2.set_title("Distribution of Future Volatility by Split")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Plot 3: Spike locations over time
    ax3 = axes[2]
    # Mark spikes (using training threshold)
    train_spikes = df_train[df_train["future_volatility"] >= tau]
    val_spikes = df_val[df_val["future_volatility"] >= tau]
    test_spikes = df_test[df_test["future_volatility"] >= tau]

    ax3.scatter(
        df_train["timestamp"],
        [1] * len(df_train),
        alpha=0.1,
        s=5,
        color="blue",
        label="Train samples",
    )
    ax3.scatter(
        df_val["timestamp"],
        [1] * len(df_val),
        alpha=0.1,
        s=5,
        color="orange",
        label="Validation samples",
    )
    ax3.scatter(
        df_test["timestamp"],
        [1] * len(df_test),
        alpha=0.1,
        s=5,
        color="green",
        label="Test samples",
    )

    if len(train_spikes) > 0:
        ax3.scatter(
            train_spikes["timestamp"],
            [1.1] * len(train_spikes),
            s=50,
            marker="^",
            color="blue",
            label=f"Train spikes ({len(train_spikes)})",
            alpha=0.7,
        )
    if len(val_spikes) > 0:
        ax3.scatter(
            val_spikes["timestamp"],
            [1.1] * len(val_spikes),
            s=50,
            marker="^",
            color="orange",
            label=f"Validation spikes ({len(val_spikes)})",
            alpha=0.7,
        )
    if len(test_spikes) > 0:
        ax3.scatter(
            test_spikes["timestamp"],
            [1.1] * len(test_spikes),
            s=50,
            marker="^",
            color="green",
            label=f"Test spikes ({len(test_spikes)})",
            alpha=0.7,
        )

    ax3.axvline(
        df_train["timestamp"].max(),
        color="black",
        linestyle=":",
        linewidth=1,
        alpha=0.5,
    )
    ax3.axvline(
        df_val["timestamp"].max(), color="black", linestyle=":", linewidth=1, alpha=0.5
    )
    ax3.set_xlabel("Timestamp")
    ax3.set_ylabel("Split")
    ax3.set_title("Volatility Spikes Across Temporal Splits")
    ax3.set_yticks([1, 1.1])
    ax3.set_yticklabels(["Samples", "Spikes"])
    ax3.legend(loc="upper left")
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()

    # Save plot
    output_dir = Path(__file__).parent.parent / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "split_distribution_analysis.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"\nVisualization saved to: {output_path}")

    plt.show()

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(
        f"""
The data is split TEMPORALLY (chronologically):
  1. Train: First {train_pct*100:.0f}% of data ({len(df_train)} samples)
  2. Validation: Next {val_pct*100:.0f}% of data ({len(df_val)} samples)
  3. Test: Last {test_pct*100:.0f}% of data ({len(df_test)} samples)

The threshold τ = {tau:.8f} is computed from TRAINING data only (95th percentile).

WHY VALIDATION HAS NO SPIKES:
  - Volatility spikes are CLUSTERED in time (not uniformly distributed)
  - The validation period happens to be a 'calm' period with no high volatility
  - Validation's maximum volatility ({df_val['future_volatility'].max():.8f}) is lower than τ
  - Therefore, NO samples in validation exceed the training threshold

WHY TEST HAS SPIKES:
  - The test period contains high volatility events
  - Test's maximum volatility ({df_test['future_volatility'].max():.8f}) exceeds τ
  - Therefore, test set has {y_test.sum()} positive samples

SOLUTIONS:
  1. Use stratified_temporal_split (already in train.py) - redistributes positives
  2. Lower the threshold percentile (e.g., 90th instead of 95th)
  3. Collect more data to ensure spikes are distributed across time periods
  4. Use a global threshold computed from ALL data (not just training)
    """
    )


if __name__ == "__main__":
    main()
