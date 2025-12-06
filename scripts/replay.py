#!/usr/bin/env python3
"""
Replay Script

Takes saved raw data (NDJSON) and regenerates features identically.
This ensures reproducibility and allows testing feature computation
without needing a live Kafka stream.
"""

import json
import argparse
import logging
from pathlib import Path
from typing import List, Dict
import glob

import pandas as pd
import yaml
from dotenv import load_dotenv

# Import feature computation functions from featurizer
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from features.featurizer import (
    parse_ticker_message,
    compute_features,
    compute_future_volatility,
)

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


def load_raw_data(file_paths: List[str]) -> List[Dict]:
    """Load raw data from NDJSON files."""
    all_tickers = []

    for file_pattern in file_paths:
        # Expand glob patterns
        files = glob.glob(file_pattern)

        for file_path in files:
            logger.info(f"Loading {file_path}...")
            try:
                with open(file_path, "r") as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue

                        try:
                            data = json.loads(line)
                            ticker_data = parse_ticker_message(data)
                            if ticker_data:
                                all_tickers.append(ticker_data)
                        except json.JSONDecodeError as e:
                            logger.warning(
                                f"Error parsing line {line_num} in {file_path}: {e}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Error processing line {line_num} in {file_path}: {e}"
                            )
            except Exception as e:
                logger.error(f"Error reading {file_path}: {e}")

    logger.info(f"Loaded {len(all_tickers)} ticker messages")
    return all_tickers


def main():
    parser = argparse.ArgumentParser(
        description="Replay raw data to regenerate features"
    )
    parser.add_argument(
        "--raw",
        type=str,
        nargs="+",
        required=True,
        help="Raw data file(s) or glob pattern(s) (e.g., data/raw/*.ndjson)",
    )
    parser.add_argument(
        "--out", type=str, default=None, help="Output Parquet file path"
    )
    parser.add_argument("--config", type=str, default=None, help="Path to config file")
    parser.add_argument(
        "--chunk_size",
        type=int,
        default=10000,
        help="Process data in chunks of this size",
    )

    args = parser.parse_args()

    # Load configuration
    if args.config:
        with open(args.config, "r") as f:
            config = yaml.safe_load(f)
    else:
        config = load_config()

    # Determine output file
    if args.out:
        output_file = Path(args.out)
    else:
        output_dir = Path(config["data"]["processed_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "features_replay.parquet"

    logger.info(f"Replaying raw data to generate features...")
    logger.info(f"Input files: {args.raw}")
    logger.info(f"Output file: {output_file}")

    # Load raw data
    all_tickers = load_raw_data(args.raw)

    if len(all_tickers) == 0:
        logger.error("No ticker data found!")
        return 1

    # Convert to DataFrame
    df = pd.DataFrame(all_tickers)

    # Ensure timestamp is datetime
    if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Sort by timestamp
    df = df.sort_values("timestamp").reset_index(drop=True)

    logger.info(f"Processing {len(df)} ticker messages")
    logger.info(f"Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")

    # Get configuration
    window_size = config["features"]["window_size"]
    horizon = config["features"]["prediction_horizon"]

    # Process in chunks if dataset is large
    if len(df) > args.chunk_size:
        logger.info(f"Processing in chunks of {args.chunk_size}...")
        all_features = []

        for i in range(0, len(df), args.chunk_size):
            chunk = df.iloc[i : i + args.chunk_size].copy()
            logger.info(
                f"Processing chunk {i//args.chunk_size + 1} ({len(chunk)} rows)..."
            )

            # Compute features
            df_features = compute_features(chunk, window_size=window_size)

            if len(df_features) > 0:
                # Compute future volatility
                df_features = compute_future_volatility(df_features, horizon=horizon)
                all_features.append(df_features)

        # Combine all chunks
        if all_features:
            df_all = pd.concat(all_features, ignore_index=True)
            df_all = df_all.sort_values("timestamp").reset_index(drop=True)
        else:
            logger.error("No features generated!")
            return 1
    else:
        # Process all at once
        logger.info("Computing features...")
        df_all = compute_features(df, window_size=window_size)

        if len(df_all) > 0:
            logger.info("Computing future volatility...")
            df_all = compute_future_volatility(df_all, horizon=horizon)
        else:
            logger.error("No features generated!")
            return 1

    # Select feature columns
    feature_cols = [
        "timestamp",
        "product_id",
        "midprice",
        "midprice_returns",
        "bid_ask_spread",
        "trade_intensity",
        "order_book_imbalance",
        "rolling_std_returns",
        "rolling_mean_spread",
        "rolling_mean_imbalance",
        "future_volatility",
    ]

    # Only include columns that exist
    available_cols = [col for col in feature_cols if col in df_all.columns]
    df_output = df_all[available_cols].copy()

    # Save to Parquet
    df_output.to_parquet(output_file, index=False)

    logger.info(f"\n✓ Successfully generated {len(df_output)} features")
    logger.info(f"  Saved to: {output_file}")
    logger.info(
        f"  Time range: {df_output['timestamp'].min()} to {df_output['timestamp'].max()}"
    )
    logger.info(f"  Columns: {list(df_output.columns)}")

    if "future_volatility" in df_output.columns:
        logger.info(f"\nFuture Volatility Statistics:")
        logger.info(f"  Mean: {df_output['future_volatility'].mean():.6f}")
        logger.info(f"  Std: {df_output['future_volatility'].std():.6f}")
        logger.info(f"  Min: {df_output['future_volatility'].min():.6f}")
        logger.info(f"  Max: {df_output['future_volatility'].max():.6f}")
        logger.info(
            f"  25th percentile: {df_output['future_volatility'].quantile(0.25):.6f}"
        )
        logger.info(
            f"  50th percentile: {df_output['future_volatility'].quantile(0.50):.6f}"
        )
        logger.info(
            f"  75th percentile: {df_output['future_volatility'].quantile(0.75):.6f}"
        )
        logger.info(
            f"  95th percentile: {df_output['future_volatility'].quantile(0.95):.6f}"
        )
        logger.info(
            f"  99th percentile: {df_output['future_volatility'].quantile(0.99):.6f}"
        )

    return 0


if __name__ == "__main__":
    exit(main())
