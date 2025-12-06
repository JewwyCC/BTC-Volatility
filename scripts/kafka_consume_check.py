#!/usr/bin/env python3
"""
Kafka Consumer Validation Script

Consumes messages from a Kafka topic to validate the stream is working.
"""

import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

import yaml
from kafka import KafkaConsumer
from kafka.errors import KafkaError
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
    parser = argparse.ArgumentParser(description="Kafka Consumer Validation")
    parser.add_argument(
        "--topic", type=str, default="ticks.raw", help="Kafka topic to consume from"
    )
    parser.add_argument(
        "--min", type=int, default=10, help="Minimum number of messages to consume"
    )
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        help="Maximum number of messages to consume (None = unlimited)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout in seconds to wait for messages",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config file (default: config.yaml)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Show full message content"
    )
    parser.add_argument(
        "--show-predictions",
        action="store_true",
        help="Show prediction values for each message (for predictions topic)",
    )

    args = parser.parse_args()

    # Load configuration
    if args.config:
        with open(args.config, "r") as f:
            config = yaml.safe_load(f)
    else:
        config = load_config()

    # Initialize Kafka consumer
    try:
        consumer = KafkaConsumer(
            args.topic,
            bootstrap_servers=config["kafka"]["bootstrap_servers"],
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            group_id="validation_consumer",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            consumer_timeout_ms=args.timeout * 1000,
        )
        logger.info(f"Connected to Kafka at {config['kafka']['bootstrap_servers']}")
        logger.info(f"Consuming from topic: {args.topic}")
    except Exception as e:
        logger.error(f"Failed to connect to Kafka: {e}")
        return 1

    message_count = 0
    sample_messages = []

    try:
        logger.info(
            f"Waiting for messages (min: {args.min}, timeout: {args.timeout}s)..."
        )

        for message in consumer:
            message_count += 1
            value = message.value

            # Store first few messages as samples
            if len(sample_messages) < 5:
                sample_messages.append(
                    {
                        "offset": message.offset,
                        "partition": message.partition,
                        "timestamp": message.timestamp,
                        "key": message.key.decode("utf-8") if message.key else None,
                        "value": value,
                    }
                )

            # Show prediction values in real-time if requested
            if (
                args.show_predictions
                and isinstance(value, dict)
                and "prediction" in value
            ):
                pred = value.get("prediction", "N/A")
                score = value.get("score", "N/A")
                prob = value.get("probability", "N/A")
                product = value.get("product_id", "N/A")
                ts = value.get("timestamp", "N/A")
                logger.info(
                    f"Msg {message_count}: {product} | Prediction: {pred} | Score: {score:.4f} | Prob: {prob:.4f} | Time: {ts}"
                )

            # Log progress
            if message_count % 100 == 0:
                logger.info(f"Consumed {message_count} messages...")

            # Check if we've reached minimum
            if message_count >= args.min:
                if args.max is None:
                    logger.info(
                        f"Reached minimum of {args.min} messages. Continue? (Ctrl+C to stop)"
                    )
                elif message_count >= args.max:
                    logger.info(f"Reached maximum of {args.max} messages")
                    break

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except KafkaError as e:
        logger.error(f"Kafka error: {e}")
        return 1
    finally:
        consumer.close()

    # Print summary
    logger.info("=" * 60)
    logger.info("CONSUMPTION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total messages consumed: {message_count}")

    if message_count < args.min:
        logger.warning(
            f"WARNING: Only consumed {message_count} messages, less than minimum {args.min}"
        )
        return 1

    if sample_messages:
        logger.info("\nSample messages:")
        for i, msg in enumerate(sample_messages[:3], 1):
            logger.info(f"\nSample {i}:")
            logger.info(f"  Offset: {msg['offset']}")
            logger.info(f"  Partition: {msg['partition']}")
            logger.info(f"  Key: {msg['key']}")
            logger.info(f"  Timestamp: {msg['timestamp']}")
            logger.info(
                f"  Value keys: {list(msg['value'].keys()) if isinstance(msg['value'], dict) else 'N/A'}"
            )
            if isinstance(msg["value"], dict):
                value = msg["value"]

                # Check if this is a prediction message
                if "prediction" in value:
                    # Show prediction-specific fields
                    logger.info(f"    product_id: {value.get('product_id', 'N/A')}")
                    logger.info(f"    timestamp: {value.get('timestamp', 'N/A')}")
                    logger.info(
                        f"    prediction: {value.get('prediction', 'N/A')} (0=no spike, 1=spike)"
                    )
                    logger.info(f"    score: {value.get('score', 'N/A')}")
                    logger.info(f"    probability: {value.get('probability', 'N/A')}")
                    logger.info(f"    model_type: {value.get('model_type', 'N/A')}")
                    if "features" in value and isinstance(value["features"], dict):
                        logger.info(f"    features: {list(value['features'].keys())}")
                else:
                    # Show common fields for other message types
                    for key in [
                        "product_id",
                        "price",
                        "time",
                        "timestamp",
                        "feature_timestamp",
                    ]:
                        if key in value:
                            logger.info(f"    {key}: {value[key]}")

                # Show full message if verbose
                if args.verbose:
                    logger.info(
                        f"    Full message: {json.dumps(value, indent=4, default=str)}"
                    )

    logger.info("\n✓ Stream validation successful!")
    return 0


if __name__ == "__main__":
    exit(main())
