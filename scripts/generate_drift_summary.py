#!/usr/bin/env python3
"""
Generate Evidently Drift Summary

Creates an Evidently report and writes a summary to docs/drift_summary.md.
This script can be scheduled to run periodically (e.g., daily) to monitor data drift.
"""

import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone

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


def generate_drift_summary(df_reference, df_current, feature_cols, output_dir):
    """Generate Evidently report and extract summary."""
    logger.info("Generating Evidently drift report...")

    # Create report with data drift and summary presets
    report = Report([DataDriftPreset(), DataSummaryPreset()])

    # Run report
    report_result = report.run(
        current_data=df_current[feature_cols], reference_data=df_reference[feature_cols]
    )

    # Save HTML report
    html_path = output_dir / "data_drift_report.html"
    report_result.save_html(str(html_path))
    logger.info(f"✓ Saved HTML report to {html_path}")

    # Get report as dictionary (Evidently API may vary by version)
    try:
        report_dict = report_result.as_dict()
    except AttributeError:
        # Fallback: try to get metrics directly
        try:
            report_dict = report_result.get_metrics()
        except Exception:
            # If all else fails, create minimal dict
            report_dict = {"metrics": []}
            logger.warning(
                "Could not extract full report dict, using minimal structure"
            )

    return report_dict, html_path


def extract_drift_summary(report_dict):
    """Extract key information from Evidently report."""
    summary = {
        "drift_detected": False,
        "drifted_features": [],
        "feature_stats": {},
        "dataset_drift": None,
        "number_of_drifted_features": 0,
        "share_of_drifted_features": 0.0,
    }

    try:
        # Extract data drift metrics
        # Handle different Evidently API versions
        metrics_list = report_dict.get("metrics", [])
        if not metrics_list and isinstance(report_dict, list):
            metrics_list = report_dict

        for metric in metrics_list:
            if isinstance(metric, dict):
                metric_name = metric.get("metric", "")
                if "DataDrift" in metric_name or metric_name == "DataDriftTable":
                    result = metric.get("result", {})

                    # Overall dataset drift
                    summary["dataset_drift"] = result.get("dataset_drift", False)
                    summary["drift_detected"] = result.get("dataset_drift", False)
                    summary["number_of_drifted_features"] = result.get(
                        "number_of_drifted_features", 0
                    )
                    summary["share_of_drifted_features"] = result.get(
                        "share_of_drifted_features", 0.0
                    )

                    # Individual feature drift
                    features = result.get("drift_by_columns", {})
                    if not features:
                        features = result.get("drift_by_column", {})

                    for feature_name, feature_data in features.items():
                        if isinstance(feature_data, dict):
                            drifted = feature_data.get(
                                " drift_detected", False
                            ) or feature_data.get("drift_detected", False)
                            if drifted:
                                summary["drifted_features"].append(
                                    {
                                        "name": feature_name,
                                        "drift_score": feature_data.get(
                                            "drift_score", 0.0
                                        ),
                                        "statistical_test": feature_data.get(
                                            "statistical_test", "unknown"
                                        ),
                                    }
                                )

                                # Store feature statistics
                                summary["feature_stats"][feature_name] = {
                                    "drift_score": feature_data.get("drift_score", 0.0),
                                    "reference_mean": feature_data.get(
                                        "reference_mean"
                                    ),
                                    "current_mean": feature_data.get("current_mean"),
                                }
    except Exception as e:
        logger.warning(f"Could not fully extract drift summary: {e}")
        import traceback

        logger.debug(traceback.format_exc())

    return summary


def write_summary_markdown(summary, df_reference, df_current, html_path, output_path):
    """Write drift summary to markdown file."""
    timestamp = datetime.now(timezone.utc).isoformat()

    markdown = f"""# Data Drift Summary

**Generated:** {timestamp}  
**Report:** {html_path}

## Executive Summary

"""

    if summary["drift_detected"]:
        markdown += f"""⚠️ **DRIFT DETECTED**

- **Dataset Drift:** {'Yes' if summary['dataset_drift'] else 'No'}
- **Drifted Features:** {summary['number_of_drifted_features']} out of {len(summary['feature_stats'])} features
- **Share of Drifted Features:** {summary['share_of_drifted_features']:.1%}

"""
    else:
        markdown += """✅ **NO DRIFT DETECTED**

- **Dataset Drift:** No
- **Drifted Features:** 0
- **All features within expected distribution**

"""

    markdown += f"""## Data Windows

- **Reference Window:**
  - Samples: {len(df_reference)}
  - Time Range: {df_reference['timestamp'].min()} to {df_reference['timestamp'].max()}

- **Current Window:**
  - Samples: {len(df_current)}
  - Time Range: {df_current['timestamp'].min()} to {df_current['timestamp'].max()}

"""

    if summary["drifted_features"]:
        markdown += """## Drifted Features

| Feature | Drift Score | Reference Mean | Current Mean | Change |
|---------|-------------|---------------|-------------|--------|
"""
        for feature in summary["drifted_features"]:
            feature_name = feature["name"]
            stats = summary["feature_stats"].get(feature_name, {})
            ref_mean = stats.get("reference_mean", "N/A")
            curr_mean = stats.get("current_mean", "N/A")
            drift_score = feature.get("drift_score", 0.0)

            # Calculate change if both means are numeric
            change = "N/A"
            if isinstance(ref_mean, (int, float)) and isinstance(
                curr_mean, (int, float)
            ):
                if ref_mean != 0:
                    change_pct = ((curr_mean - ref_mean) / abs(ref_mean)) * 100
                    change = f"{change_pct:+.1f}%"
                else:
                    change = f"{curr_mean - ref_mean:+.4f}"

            markdown += f"| {feature_name} | {drift_score:.4f} | {ref_mean} | {curr_mean} | {change} |\n"

        markdown += "\n"

    markdown += """## Recommendations

"""

    if summary["drift_detected"]:
        markdown += """1. **Review Drifted Features**: Investigate features with high drift scores
2. **Check Data Pipeline**: Verify no upstream changes affecting feature distributions
3. **Monitor Model Performance**: Watch for degradation in model predictions
4. **Consider Retraining**: If drift is significant (>0.3 drift score), consider model retraining
5. **Update Reference Window**: If drift is expected (e.g., market regime change), update reference window

"""
    else:
        markdown += """✅ No action required. Data distributions are stable.

"""

    markdown += f"""## Full Report

For detailed analysis, see the HTML report: `{html_path}`

## Next Steps

1. Review this summary and the HTML report
2. If drift is detected, investigate root causes
3. Monitor model performance metrics
4. Schedule model retraining if necessary
5. Update reference window if drift is expected and acceptable

---
*This report was generated automatically. Review regularly to ensure model performance.*
"""

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(markdown)

    logger.info(f"✓ Saved drift summary to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate Evidently Drift Summary")
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
        help="Output directory for HTML reports",
    )
    parser.add_argument(
        "--summary_path",
        type=str,
        default="docs/drift_summary.md",
        help="Path to write drift summary markdown",
    )
    parser.add_argument(
        "--train_pct",
        type=float,
        default=0.7,
        help="Percentage of data used for training (default: 0.7 = 70%)",
    )
    parser.add_argument(
        "--val_pct",
        type=float,
        default=0.1,
        help="Percentage of data used for validation (default: 0.1 = 10%)",
    )
    parser.add_argument("--config", type=str, default=None, help="Path to config file")

    args = parser.parse_args()

    # Load configuration
    if args.config:
        with open(args.config, "r") as f:
            yaml.safe_load(f)
    else:
        load_config()

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

    # Split into reference (training) and current (test) windows
    n_train = int(len(df) * args.train_pct)
    n_val = int(len(df) * args.val_pct)

    df_reference = df.iloc[:n_train].copy()  # Training data (reference)
    df_current = df.iloc[n_train + n_val :].copy()  # Test data (current)

    logger.info("\nData Split:")
    logger.info(
        f"  Reference (Training): {len(df_reference)} samples ({args.train_pct*100:.1f}%)"
    )
    logger.info(
        f"    Time range: {df_reference['timestamp'].min()} to {df_reference['timestamp'].max()}"
    )
    logger.info(
        f"  Current (Test): {len(df_current)} samples ({(1-args.train_pct-args.val_pct)*100:.1f}%)"
    )
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

    # Select only feature columns for comparison
    cols_to_compare = available_features + (
        ["future_volatility"] if "future_volatility" in df.columns else []
    )

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate drift report and summary
    report_dict, html_path = generate_drift_summary(
        df_reference[cols_to_compare],
        df_current[cols_to_compare],
        cols_to_compare,
        output_dir,
    )

    # Extract summary
    summary = extract_drift_summary(report_dict)

    # Write markdown summary
    summary_path = Path(args.summary_path)
    write_summary_markdown(summary, df_reference, df_current, html_path, summary_path)

    # Print summary to console
    logger.info("\n" + "=" * 60)
    logger.info("DRIFT SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Dataset Drift: {'YES' if summary['drift_detected'] else 'NO'}")
    logger.info(f"Drifted Features: {summary['number_of_drifted_features']}")
    logger.info(
        f"Share of Drifted Features: {summary['share_of_drifted_features']:.1%}"
    )

    if summary["drifted_features"]:
        logger.info("\nDrifted Features:")
        for feature in summary["drifted_features"]:
            logger.info(
                f"  - {feature['name']}: drift_score={feature['drift_score']:.4f}"
            )

    logger.info(f"\nSummary written to: {summary_path}")
    logger.info(f"Full report: {html_path}")

    return 0


if __name__ == "__main__":
    exit(main())
