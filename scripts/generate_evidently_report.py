#!/usr/bin/env python3
"""
Generate Evidently Report

Creates an Evidently report comparing early and late windows of data
to detect drift and data quality issues.
"""

import argparse
import logging
from pathlib import Path

import pandas as pd
import yaml
from evidently import Report
from evidently.presets import DataDriftPreset, DataSummaryPreset
from dotenv import load_dotenv

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


def main():
    parser = argparse.ArgumentParser(description="Generate Evidently Report")
    parser.add_argument(
        "--features",
        type=str,
        default="data/processed/features.parquet",
        help="Path to features Parquet file",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="reports/evidently",
        help="Output directory for reports",
    )
    parser.add_argument(
        "--train_pct",
        type=float,
        default=0.7,
        help="Percentage of data used for training (default: 0.7 = 70%%)",
    )
    parser.add_argument(
        "--val_pct",
        type=float,
        default=0.1,
        help="Percentage of data used for validation (default: 0.1 = 10%%)",
    )
    parser.add_argument(
        "--compare_mode",
        type=str,
        default="train_test",
        choices=["train_test", "early_late"],
        help="Comparison mode: train_test (default) or early_late",
    )
    parser.add_argument("--config", type=str, default=None, help="Path to config file")

    args = parser.parse_args()

    # Load configuration
    if args.config:
        with open(args.config, "r") as f:
            config = yaml.safe_load(f)  # noqa: F841
    else:
        config = load_config()  # noqa: F841

    # Load features
    logger.info(f"Loading features from {args.features}...")
    df = pd.read_parquet(args.features)

    # Ensure timestamp is datetime
    if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Sort by timestamp
    df = df.sort_values("timestamp").reset_index(drop=True)

    logger.info(f"Loaded {len(df)} feature rows")
    logger.info(f"Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")

    # Split based on comparison mode
    if args.compare_mode == "train_test":
        # Use train/test split (matching model training)
        n_train = int(len(df) * args.train_pct)
        n_val = int(len(df) * args.val_pct)
        test_pct = 1 - args.train_pct - args.val_pct

        df_reference = df.iloc[:n_train].copy()  # Training data
        df_current = df.iloc[n_train + n_val :].copy()  # Test data

        logger.info("\nTrain/Test Split (for drift detection):")
        logger.info(
            f"  Reference (Training): {len(df_reference)} samples ({args.train_pct*100:.1f}%)"
        )
        logger.info(
            f"    Time range: {df_reference['timestamp'].min()} to {df_reference['timestamp'].max()}"
        )
        logger.info(
            f"  Current (Test): {len(df_current)} samples ({test_pct*100:.1f}%)"
        )
        logger.info(
            f"    Time range: {df_current['timestamp'].min()} to {df_current['timestamp'].max()}"
        )
    else:
        # Early/late window split (original behavior)
        n_early = int(len(df) * (1 - args.val_pct - (1 - args.train_pct)) / 2)
        n_late = int(len(df) * (1 - args.val_pct - (1 - args.train_pct)) / 2)

        df_reference = df.iloc[:n_early].copy()
        df_current = df.iloc[-n_late:].copy()

        logger.info("\nEarly/Late Window Split:")
        logger.info(f"  Reference (Early): {len(df_reference)} samples")
        logger.info(
            f"    Time range: {df_reference['timestamp'].min()} to {df_reference['timestamp'].max()}"
        )
        logger.info(f"  Current (Late): {len(df_current)} samples")
        logger.info(
            f"    Time range: {df_current['timestamp'].min()} to {df_current['timestamp'].max()}"
        )

    # Define feature columns
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

    # Select only feature columns for comparison (exclude timestamp, product_id)
    cols_to_compare = available_features + (
        ["future_volatility"] if "future_volatility" in df.columns else []
    )

    df_reference_compare = df_reference[cols_to_compare].copy()
    df_current_compare = df_current[cols_to_compare].copy()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate Data Drift Report
    logger.info("\nGenerating Data Drift Report...")
    drift_report = Report([DataDriftPreset()])
    drift_eval = drift_report.run(
        current_data=df_current_compare, reference_data=df_reference_compare
    )

    # Save drift report
    drift_report_path = output_dir / "data_drift_report.html"
    drift_eval.save_html(str(drift_report_path))
    logger.info(f"✓ Saved drift report to {drift_report_path}")

    # Generate Data Summary Report (for data quality)
    logger.info("Generating Data Summary Report...")
    summary_report = Report([DataSummaryPreset()])
    summary_eval = summary_report.run(
        current_data=df_current_compare, reference_data=df_reference_compare
    )

    # Save summary report
    summary_report_path = output_dir / "data_summary_report.html"
    summary_eval.save_html(str(summary_report_path))
    logger.info(f"✓ Saved summary report to {summary_report_path}")

    # Generate Combined Report
    logger.info("Generating Combined Report...")
    combined_report = Report([DataDriftPreset(), DataSummaryPreset()])
    combined_eval = combined_report.run(
        current_data=df_current_compare, reference_data=df_reference_compare
    )

    # Save combined report
    combined_report_path = output_dir / "combined_report.html"
    combined_eval.save_html(str(combined_report_path))
    logger.info(f"✓ Saved combined report to {combined_report_path}")

    # Save JSON profile
    json_profile_path = output_dir / "profile.json"
    with open(json_profile_path, "w") as f:
        f.write(combined_eval.json())
    logger.info(f"✓ Saved JSON profile to {json_profile_path}")

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("REPORT SUMMARY")
    logger.info("=" * 60)

    # Get drift summary from the evaluation result
    try:
        drift_eval.as_dict()
        logger.info("Dataset Drift: Check HTML reports for detailed analysis")
        # The dict structure may vary, but we can log that reports were generated
    except Exception as e:
        logger.debug(f"Could not extract drift summary: {e}")

    logger.info(f"\nReports saved to: {output_dir}")
    logger.info(f"  - Data Drift: {drift_report_path}")
    logger.info(f"  - Data Summary: {summary_report_path}")
    logger.info(f"  - Combined: {combined_report_path}")
    logger.info(f"  - JSON Profile: {json_profile_path}")

    return 0


if __name__ == "__main__":
    exit(main())
