#!/usr/bin/env python3
"""
Coinbase Advanced Trade WebSocket Ingestor

Connects to Coinbase's WebSocket API, collects ticker data,
and publishes to Kafka topic 'ticks.raw'.
"""

import json
import time
import argparse
import logging
import signal
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import websocket
import yaml
from kafka import KafkaProducer
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

# Global variables for graceful shutdown
producer: Optional[KafkaProducer] = None
ws: Optional[websocket.WebSocketApp] = None
running = True
message_count = 0
start_time = None


def load_config():
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    global running, producer, ws
    logger.info("Shutting down gracefully...")
    running = False
    if ws:
        ws.close()
    if producer:
        producer.close()


def on_message(ws, message):
    """Handle incoming WebSocket messages"""
    global message_count, producer, config
    
    try:
        data = json.loads(message)
        
        # Skip heartbeat messages (they're just for keeping connection alive)
        if data.get('channel') == 'heartbeats' or data.get('type') == 'heartbeat':
            return
        
        # Skip subscription confirmations
        if data.get('type') in ['subscriptions', 'error']:
            logger.debug(f"Received {data.get('type')}: {data}")
            return
        
        # Extract product_id from various possible fields
        product_id = (
            data.get('product_id') or 
            data.get('product_ids', [None])[0] if isinstance(data.get('product_ids'), list) else None or
            'unknown'
        )
        
        # Add ingestion timestamp
        data['ingestion_timestamp'] = datetime.now(timezone.utc).isoformat()
        
        # Serialize message once
        message_json = json.dumps(data)
        value_bytes = message_json.encode("utf-8")
        key_bytes = str(product_id).encode("utf-8")

        # --- Retry sending to Kafka explicitly ---
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                future = producer.send(
                    config["kafka"]["topics"]["raw"],
                    value=value_bytes,
                    key=key_bytes,
                )
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

        
        # Optionally mirror to local file
        if config.get('data', {}).get('raw_dir'):
            raw_dir = Path(config['data']['raw_dir'])
            raw_dir.mkdir(parents=True, exist_ok=True)
            
            # Write to NDJSON file (append mode)
            raw_file = raw_dir / f"ticks_{datetime.now(timezone.utc).strftime('%Y%m%d')}.ndjson"
            with open(raw_file, 'a') as f:
                f.write(message_json + '\n')
        
        message_count += 1
        
        # Log every 100 messages
        if message_count % 100 == 0:
            logger.info(f"Processed {message_count} messages")
            
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
    except KafkaError as e:
        logger.error(f"Kafka error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")


def on_error(ws, error):
    """Handle WebSocket errors"""
    logger.error(f"WebSocket error: {error}")


def on_close(ws, close_status_code, close_msg):
    """Handle WebSocket close"""
    logger.info(f"WebSocket connection closed (code: {close_status_code}, msg: {close_msg})")
    # Reconnection will be handled by the run_ws_with_reconnect function


def on_open(ws):
    """Handle WebSocket open and subscribe to channels"""
    logger.info("WebSocket connection opened")
    
    product_id = config['coinbase'].get('product_id', 'BTC-USD')
    
    # Subscribe to heartbeats channel first (recommended best practice)
    # This keeps the connection alive during periods of low activity
    heartbeat_subscribe = {
        "type": "subscribe",
        "channel": "heartbeats"
    }
    ws.send(json.dumps(heartbeat_subscribe))
    logger.info("Subscribed to heartbeats channel")
    
    # Small delay between subscriptions
    time.sleep(0.1)
    
    # Subscribe to ticker channel for the trading pair
    ticker_subscribe = {
        "type": "subscribe",
        "product_ids": [product_id],
        "channel": "ticker"
    }
    ws.send(json.dumps(ticker_subscribe))
    logger.info(f"Subscribed to ticker channel for {product_id}")


def main():
    global producer, ws, config, start_time
    
    parser = argparse.ArgumentParser(description='Coinbase WebSocket Ingestor')
    parser.add_argument('--pair', type=str, default='BTC-USD',
                       help='Trading pair (e.g., BTC-USD)')
    parser.add_argument('--minutes', type=int, default=None,
                       help='Run for specified minutes (None = run indefinitely)')
    parser.add_argument('--config', type=str, default=None,
                       help='Path to config file (default: config.yaml)')
    
    args = parser.parse_args()
    
    # Load configuration
    if args.config:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
    else:
        config = load_config()
    
    # Override product_id from command line
    if 'coinbase' not in config:
        config['coinbase'] = {}
    config['coinbase']['product_id'] = args.pair
    
    # Set up signal handlers
    # Register signal handlers so Ctrl-C / Docker stop will trigger a graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize Kafka producer
    try:
        producer = KafkaProducer(
            bootstrap_servers=config['kafka']['bootstrap_servers'],
            value_serializer=lambda v: v,
            key_serializer=lambda k: k,
            acks='all',
            retries=3
        )
        logger.info(f"Connected to Kafka at {config['kafka']['bootstrap_servers']}")
    except Exception as e:
        logger.error(f"Failed to connect to Kafka: {e}")
        sys.exit(1)
    
    # Build WebSocket URL
    ws_url = config['coinbase']['ws_url']
    
    # Create WebSocket connection
    ws = websocket.WebSocketApp(
        ws_url,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open
    )
    
    start_time = time.time()
    logger.info(f"Starting ingestion for {args.pair}...")
    
    # Run WebSocket in a separate thread
    import threading
    
    def run_ws():
        ws.run_forever()
    
    ws_thread = threading.Thread(target=run_ws, daemon=True)
    ws_thread.start()
    
    # Main loop with timeout
    try:
        while running:
            time.sleep(1)
            
            # Check if we've exceeded time limit
            if args.minutes:
                elapsed = time.time() - start_time
                if elapsed >= args.minutes * 60:
                    logger.info(f"Reached time limit of {args.minutes} minutes")
                    break
            
            # Check if WebSocket thread is still alive (reconnect if not)
            # If the WebSocket thread died unexpectedly, try to reconnect
            if not ws_thread.is_alive() and running:
                logger.warning("WebSocket thread died. Attempting reconnection...")
                reconnect_delay = config['coinbase'].get('reconnect_delay', 5)
                time.sleep(reconnect_delay)
                # Recreate WebSocket connection
                ws = websocket.WebSocketApp(
                    ws_url,
                    on_message=on_message,
                    on_error=on_error,
                    on_close=on_close,
                    on_open=on_open
                )
                ws_thread = threading.Thread(target=run_ws, daemon=True)
                ws_thread.start()
                logger.info("Reconnected WebSocket")
    
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        signal_handler(None, None)
        elapsed = time.time() - start_time if start_time else 0
        logger.info(f"Total messages ingested: {message_count}")
        if elapsed > 0:
            logger.info(f"Total runtime: {elapsed:.2f} seconds")
            logger.info(f"Average rate: {message_count / elapsed:.2f} messages/second")


if __name__ == "__main__":
    main()

