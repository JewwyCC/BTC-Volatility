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
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config():
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description='Kafka Consumer Validation')
    parser.add_argument('--topic', type=str, default='ticks.raw',
                       help='Kafka topic to consume from')
    parser.add_argument('--min', type=int, default=10,
                       help='Minimum number of messages to consume')
    parser.add_argument('--max', type=int, default=None,
                       help='Maximum number of messages to consume (None = unlimited)')
    parser.add_argument('--timeout', type=int, default=30,
                       help='Timeout in seconds to wait for messages')
    parser.add_argument('--config', type=str, default=None,
                       help='Path to config file (default: config.yaml)')
    
    args = parser.parse_args()
    
    # Load configuration
    if args.config:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
    else:
        config = load_config()
    
    # Initialize Kafka consumer
    try:
        consumer = KafkaConsumer(
            args.topic,
            bootstrap_servers=config['kafka']['bootstrap_servers'],
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            group_id='validation_consumer',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            consumer_timeout_ms=args.timeout * 1000
        )
        logger.info(f"Connected to Kafka at {config['kafka']['bootstrap_servers']}")
        logger.info(f"Consuming from topic: {args.topic}")
    except Exception as e:
        logger.error(f"Failed to connect to Kafka: {e}")
        return 1
    
    message_count = 0
    sample_messages = []
    
    try:
        logger.info(f"Waiting for messages (min: {args.min}, timeout: {args.timeout}s)...")
        
        for message in consumer:
            message_count += 1
            value = message.value
            
            # Store first few messages as samples
            if len(sample_messages) < 5:
                sample_messages.append({
                    'offset': message.offset,
                    'partition': message.partition,
                    'timestamp': message.timestamp,
                    'key': message.key.decode('utf-8') if message.key else None,
                    'value': value
                })
            
            # Log progress
            if message_count % 100 == 0:
                logger.info(f"Consumed {message_count} messages...")
            
            # Check if we've reached minimum
            if message_count >= args.min:
                if args.max is None:
                    logger.info(f"Reached minimum of {args.min} messages. Continue? (Ctrl+C to stop)")
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
        logger.warning(f"WARNING: Only consumed {message_count} messages, less than minimum {args.min}")
        return 1
    
    if sample_messages:
        logger.info("\nSample messages:")
        for i, msg in enumerate(sample_messages[:3], 1):
            logger.info(f"\nSample {i}:")
            logger.info(f"  Offset: {msg['offset']}")
            logger.info(f"  Partition: {msg['partition']}")
            logger.info(f"  Key: {msg['key']}")
            logger.info(f"  Timestamp: {msg['timestamp']}")
            logger.info(f"  Value keys: {list(msg['value'].keys()) if isinstance(msg['value'], dict) else 'N/A'}")
            if isinstance(msg['value'], dict):
                # Show a few key fields
                for key in ['product_id', 'price', 'time', 'timestamp']:
                    if key in msg['value']:
                        logger.info(f"    {key}: {msg['value'][key]}")
    
    logger.info("\n✓ Stream validation successful!")
    return 0


if __name__ == "__main__":
    exit(main())

