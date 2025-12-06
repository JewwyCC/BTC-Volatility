#!/usr/bin/env python3
"""
Feature Engineering Pipeline

Kafka consumer that computes windowed features from ticker data:
- Midprice returns
- Bid-ask spread
- Trade intensity
- Order-book imbalance (optional)

Outputs to Kafka topic 'ticks.features' and saves to Parquet.
"""

import json
import argparse
import logging
import signal
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd
import numpy as np
import yaml
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global variables for graceful shutdown
consumer: Optional[KafkaConsumer] = None
producer: Optional[KafkaProducer] = None
running = True


def load_config():
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    global running, consumer, producer
    logger.info("Shutting down gracefully...")
    running = False
    if consumer:
        consumer.close()
    if producer:
        producer.flush()
        producer.close()
    sys.exit(0)


def parse_ticker_message(message_data: Dict) -> Optional[Dict]:
    """
    Parse a ticker message and extract relevant fields.

    Returns a dict with: timestamp, product_id, price, best_bid, best_ask,
    best_bid_quantity, best_ask_quantity, or None if not a ticker message.
    """
    if message_data.get("channel") != "ticker":
        return None

    events = message_data.get("events", [])
    if not events:
        return None

    # Extract ticker data from events
    for event in events:
        tickers = event.get("tickers", [])
        for ticker in tickers:
            if ticker.get("type") == "ticker":
                try:
                    # Parse timestamp
                    ts_str = message_data.get("timestamp", "")
                    if ts_str:
                        # Parse ISO format timestamp
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    else:
                        ts = datetime.now(timezone.utc)

                    # Extract numeric values
                    price = float(ticker.get("price", 0))
                    best_bid = float(ticker.get("best_bid", 0))
                    best_ask = float(ticker.get("best_ask", 0))
                    best_bid_qty = float(ticker.get("best_bid_quantity", 0))
                    best_ask_qty = float(ticker.get("best_ask_quantity", 0))

                    return {
                        "timestamp": ts,
                        "product_id": ticker.get("product_id", ""),
                        "price": price,
                        "best_bid": best_bid,
                        "best_ask": best_ask,
                        "best_bid_quantity": best_bid_qty,
                        "best_ask_quantity": best_ask_qty,
                        "sequence_num": message_data.get("sequence_num", 0),
                    }
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parsing ticker: {e}")
                    return None

    return None


def compute_features(df: pd.DataFrame, window_size: int = 60) -> pd.DataFrame:
    """
    Compute windowed features from tick data.

    Features:
    - midprice: (best_bid + best_ask) / 2
    - midprice_returns: log returns of midprice
    - bid_ask_spread: (best_ask - best_bid) / midprice (relative spread)
    - trade_intensity: number of ticks per second
    - order_book_imbalance: (best_bid_qty - best_ask_qty) / (best_bid_qty + best_ask_qty)
    - rolling_std_returns: rolling standard deviation of returns over window_size seconds
    """
    if len(df) == 0:
        return pd.DataFrame()

    # Sort by timestamp
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Compute midprice
    df["midprice"] = (df["best_bid"] + df["best_ask"]) / 2

    # Compute log returns
    df["midprice_returns"] = np.log(df["midprice"] / df["midprice"].shift(1))

    # Compute relative bid-ask spread
    df["bid_ask_spread"] = (df["best_ask"] - df["best_bid"]) / df["midprice"]

    # Compute order book imbalance
    total_qty = df["best_bid_quantity"] + df["best_ask_quantity"]
    df["order_book_imbalance"] = np.where(
        total_qty > 0,
        (df["best_bid_quantity"] - df["best_ask_quantity"]) / total_qty,
        0.0,
    )

    # Set timestamp as index for time-based operations
    df_indexed = df.set_index("timestamp")

    # Compute rolling features over window_size seconds
    window_str = f"{window_size}s"

    # Rolling standard deviation of returns
    df_indexed["rolling_std_returns"] = (
        df_indexed["midprice_returns"].rolling(window=window_str, min_periods=2).std()
    )

    # Trade intensity: number of ticks per second in window
    df_indexed["trade_intensity"] = (
        df_indexed["midprice"].rolling(window=window_str, min_periods=1).count()
        / window_size
    )

    # Rolling mean of spread
    df_indexed["rolling_mean_spread"] = (
        df_indexed["bid_ask_spread"].rolling(window=window_str, min_periods=1).mean()
    )

    # Rolling mean of order book imbalance
    df_indexed["rolling_mean_imbalance"] = (
        df_indexed["order_book_imbalance"]
        .rolling(window=window_str, min_periods=1)
        .mean()
    )

    # Reset index to get timestamp back as column
    result = df_indexed.reset_index()

    # Drop rows with NaN (first row has no return, etc.)
    result = result.dropna(subset=["midprice_returns", "rolling_std_returns"])

    return result


def compute_future_volatility(df: pd.DataFrame, horizon: int = 60) -> pd.DataFrame:
    """
    Compute future volatility (rolling std of returns) over the next 'horizon' seconds.
    This will be used as the target variable.

    For each timestamp t, computes the standard deviation of returns from t+1 to t+horizon.
    Since pandas rolling() only looks backward, we use a manual forward-looking approach.
    """
    if len(df) == 0:
        return df

    df_indexed = df.set_index("timestamp").sort_index()
    returns = df_indexed["midprice_returns"].copy()

    # Initialize future volatility column
    future_vol = pd.Series(index=df_indexed.index, dtype=float)

    # For each timestamp, compute std of returns in the next 'horizon' seconds
    for i, (ts, _) in enumerate(df_indexed.iterrows()):
        # Find all timestamps within the next 'horizon' seconds (excluding current)
        end_time = ts + pd.Timedelta(seconds=horizon)

        # Get returns from next timestamp to end_time
        future_mask = (df_indexed.index > ts) & (df_indexed.index <= end_time)
        future_returns = returns[future_mask]

        if len(future_returns) >= 2:  # Need at least 2 points for std
            future_vol.loc[ts] = future_returns.std()
        else:
            future_vol.loc[ts] = np.nan

    df_indexed["future_volatility"] = future_vol

    # Reset index
    result = df_indexed.reset_index()

    return result


def process_message_buffer(
    buffer: List[Dict], config: Dict, producer: Optional[KafkaProducer] = None
) -> pd.DataFrame:
    """Process a buffer of messages and compute features."""
    if len(buffer) < 2:
        return pd.DataFrame()

    # Convert to DataFrame
    df = pd.DataFrame(buffer)

    # Ensure timestamp is datetime
    if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Compute features
    window_size = config["features"]["window_size"]
    df_features = compute_features(df, window_size=window_size)

    if len(df_features) == 0:
        return df_features

    # Compute future volatility
    horizon = config["features"]["prediction_horizon"]
    df_features = compute_future_volatility(df_features, horizon=horizon)

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
    available_cols = [col for col in feature_cols if col in df_features.columns]
    df_output = df_features[available_cols].copy()

    # Publish to Kafka if producer is available
    if producer:
        topic = config["kafka"]["topics"]["features"]
        for _, row in df_output.iterrows():
            try:
                message = row.to_dict()
                # Convert datetime to ISO string for JSON serialization
                if pd.notna(message.get("timestamp")):
                    if isinstance(message["timestamp"], pd.Timestamp):
                        message["timestamp"] = message["timestamp"].isoformat()

                message_json = json.dumps(message, default=str)
                value_bytes = message_json.encode("utf-8")
                key_bytes = str(message.get("product_id", "unknown")).encode("utf-8")

                # Retry sending to Kafka explicitly
                max_attempts = 3
                for attempt in range(1, max_attempts + 1):
                    try:
                        future = producer.send(topic, value=value_bytes, key=key_bytes)
                        # Wait for Kafka to confirm it was written
                        future.get(timeout=10)
                        break  # success → leave the retry loop
                    except KafkaError as e:
                        logger.warning(
                            "Kafka send failed (attempt %d/%d): %s",
                            attempt,
                            max_attempts,
                            e,
                        )
                        # Small pause before the next try
                        time.sleep(1)

                        # If this was the last attempt, record a hard error
                        if attempt == max_attempts:
                            logger.error(
                                "Giving up on message after %d failed Kafka attempts",
                                max_attempts,
                )
            except Exception as e:
                logger.error(f"Error publishing feature: {e}")

    return df_output


def main():
    global consumer, producer, running

    parser = argparse.ArgumentParser(description="Feature Engineering Pipeline")
    parser.add_argument(
        "--topic_in", type=str, default="ticks.raw", help="Input Kafka topic"
    )
    parser.add_argument(
        "--topic_out", type=str, default="ticks.features", help="Output Kafka topic"
    )
    parser.add_argument(
        "--buffer_size",
        type=int,
        default=1000,
        help="Number of messages to buffer before processing",
    )
    parser.add_argument(
        "--output", type=str, default=None, help="Output Parquet file path (optional)"
    )
    parser.add_argument("--config", type=str, default=None, help="Path to config file")

    args = parser.parse_args()

    # Load configuration
    if args.config:
        with open(args.config, "r") as f:
            config = yaml.safe_load(f)
    else:
        config = load_config()

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize Kafka consumer
    try:
        consumer = KafkaConsumer(
            args.topic_in,
            bootstrap_servers=config["kafka"]["bootstrap_servers"],
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            group_id=config["kafka"]["consumer_group"] + "_featurizer",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            consumer_timeout_ms=5000,  # 5 second timeout
        )
        logger.info(f"Connected to Kafka, consuming from {args.topic_in}")
    except Exception as e:
        logger.error(f"Failed to connect to Kafka: {e}")
        return 1

    # Initialize Kafka producer
    try:
        producer = KafkaProducer(
            bootstrap_servers=config["kafka"]["bootstrap_servers"],
            value_serializer=lambda v: v,
            key_serializer=lambda k: k,
            acks="all",
            retries=3,
        )
        logger.info(f"Connected to Kafka producer, publishing to {args.topic_out}")
    except Exception as e:
        logger.error(f"Failed to create Kafka producer: {e}")
        return 1

    # Message buffer
    buffer: List[Dict] = []
    all_features = []
    message_count = 0
    feature_count = 0

    # Output directory
    output_dir = Path(config["data"]["processed_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    # Output file
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = output_dir / "features.parquet"

    try:
        logger.info("Starting feature computation...")

        for message in consumer:
            if not running:
                logger.info("Shutdown signal received, stopping...")
                break
            message_count += 1

            # Parse ticker message
            ticker_data = parse_ticker_message(message.value)

            if ticker_data:
                buffer.append(ticker_data)

                # Process buffer when it reaches threshold
                if len(buffer) >= args.buffer_size:
                    df_features = process_message_buffer(buffer, config, producer)

                    if len(df_features) > 0:
                        all_features.append(df_features)
                        feature_count += len(df_features)
                        logger.info(
                            f"Processed {len(buffer)} messages, generated {len(df_features)} features (total: {feature_count})"
                        )

                    # Clear buffer (keep last few for continuity)
                    buffer = buffer[
                        -100:
                    ]  # Keep last 100 for rolling window continuity

            # Log progress
            if message_count % 1000 == 0:
                logger.info(
                    f"Processed {message_count} messages, generated {feature_count} features"
                )

        # Process remaining buffer
        if len(buffer) > 0:
            df_features = process_message_buffer(buffer, config, producer)
            if len(df_features) > 0:
                all_features.append(df_features)
                feature_count += len(df_features)
                logger.info(
                    f"Final processing: {len(buffer)} messages, {len(df_features)} features"
                )

        # Flush producer
        producer.flush()

        # Combine all features and save to Parquet
        if all_features:
            df_all = pd.concat(all_features, ignore_index=True)
            df_all = df_all.sort_values("timestamp").reset_index(drop=True)

            # Save to Parquet
            df_all.to_parquet(output_file, index=False)
            logger.info(f"Saved {len(df_all)} features to {output_file}")

            # Print summary statistics
            logger.info("\nFeature Summary:")
            logger.info(f"  Total features: {len(df_all)}")
            logger.info(
                f"  Time range: {df_all['timestamp'].min()} to {df_all['timestamp'].max()}"
            )
            logger.info(f"  Columns: {list(df_all.columns)}")
            if "future_volatility" in df_all.columns:
                logger.info("  Future volatility stats:")
                logger.info(f"    Mean: {df_all['future_volatility'].mean():.6f}")
                logger.info(f"    Std: {df_all['future_volatility'].std():.6f}")
                logger.info(f"    Min: {df_all['future_volatility'].min():.6f}")
                logger.info(f"    Max: {df_all['future_volatility'].max():.6f}")
        else:
            logger.warning("No features generated!")

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1
    finally:
        consumer.close()
        producer.close()

    return 0


if __name__ == "__main__":
    exit(main())
