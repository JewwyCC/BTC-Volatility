#!/usr/bin/env python3
"""
Kafka Streaming Predictor

Consumes feature messages from Kafka topic 'ticks.features', loads model from MLflow,
makes predictions, and publishes results to 'ticks.predictions' topic.
"""

import json
import argparse
import logging
import signal
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional
import numpy as np
import pandas as pd
import yaml
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from dotenv import load_dotenv

# MLflow imports
try:
    import mlflow
    import mlflow.sklearn
    import mlflow.xgboost
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    logging.warning("MLflow not available")

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variables for graceful shutdown
consumer: Optional[KafkaConsumer] = None
producer: Optional[KafkaProducer] = None
model = None
running = True


def load_config():
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    global consumer, producer, running
    logger.info("Shutdown signal received, stopping...")
    running = False
    
    if consumer:
        consumer.close()
    if producer:
        producer.flush()
        producer.close()
    sys.exit(0)


def load_model_from_local(project_root: Path, model_type: str = 'xgboost'):
    """Load model from local artifacts directory."""
    try:
        import joblib
        import pickle
        
        artifacts_dir = project_root / "models" / "artifacts"
        
        if model_type == 'xgboost':
            model_path = artifacts_dir / "xgb_model.pkl"
        else:
            model_path = artifacts_dir / "logistic_model.pkl"
        
        if not model_path.exists():
            logger.warning(f"Local model not found at {model_path}")
            return None
        
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        
        logger.info(f"Loaded model from local path: {model_path}")
        return model
        
    except Exception as e:
        logger.warning(f"Could not load model from local path: {e}")
        return None


def load_model_from_mlflow(config: Dict, project_root: Path) -> Optional[object]:
    """Load model from MLflow with fallback to local artifacts."""
    mlflow_config = config.get('mlflow', {})
    model_source = mlflow_config.get('model_source', 'latest')
    model_type = mlflow_config.get('model_type', 'xgboost')
    
    # If explicitly set to local, skip MLflow
    if model_source == 'local':
        logger.info("Model source set to 'local', loading from artifacts")
        return load_model_from_local(project_root, model_type)
    
    # Try MLflow first
    if not MLFLOW_AVAILABLE:
        logger.warning("MLflow not available, falling back to local artifacts")
        return load_model_from_local(project_root, model_type)
    
    mlflow_uri = mlflow_config.get('tracking_uri', 'http://localhost:5001')
    experiment_name = mlflow_config.get('experiment_name', 'volatility_detection')
    run_id = mlflow_config.get('run_id')
    
    try:
        mlflow.set_tracking_uri(mlflow_uri)
        logger.info(f"Connecting to MLflow at {mlflow_uri}")
        
        # Get experiment
        experiment = mlflow.get_experiment_by_name(experiment_name)
        if experiment is None:
            logger.warning(f"Experiment '{experiment_name}' not found in MLflow, falling back to local artifacts")
            return load_model_from_local(project_root, model_type)
        experiment_id = experiment.experiment_id
        
        # Determine which run to load
        target_run_id = None
        if model_source == 'run_id' and run_id:
            target_run_id = run_id
            logger.info(f"Loading model from specified run_id: {target_run_id}")
        elif model_source == 'latest':
            # Get latest run from experiment
            runs = mlflow.search_runs(
                experiment_ids=[experiment_id],
                order_by=["start_time DESC"],
                max_results=1
            )
            if runs.empty:
                logger.warning(f"No runs found in experiment '{experiment_name}', falling back to local artifacts")
                return load_model_from_local(project_root, model_type)
            target_run_id = runs.iloc[0]['run_id']
            logger.info(f"Loading latest model from run_id: {target_run_id}")
        else:
            logger.warning(f"Invalid model_source: {model_source}, falling back to local artifacts")
            return load_model_from_local(project_root, model_type)
        
        # Load model based on type
        try:
            if model_type == 'xgboost':
                loaded_model = mlflow.xgboost.load_model(f"runs:/{target_run_id}/model")
                logger.info(f"Loaded XGBoost model from MLflow run {target_run_id}")
            else:
                loaded_model = mlflow.sklearn.load_model(f"runs:/{target_run_id}/model")
                logger.info(f"Loaded sklearn model from MLflow run {target_run_id}")
            
            return loaded_model
        except Exception as e:
            logger.warning(f"Could not load model from MLflow: {e}, falling back to local artifacts")
            return load_model_from_local(project_root, model_type)
        
    except Exception as e:
        logger.warning(f"Error connecting to MLflow: {e}, falling back to local artifacts")
        return load_model_from_local(project_root, model_type)


def transform_features(feature_data: Dict) -> Optional[np.ndarray]:
    """
    Transform feature message to model input format.
    
    Expected feature columns:
    - midprice_returns
    - bid_ask_spread
    - trade_intensity
    - order_book_imbalance
    - rolling_std_returns
    - rolling_mean_spread
    - rolling_mean_imbalance
    """
    feature_cols = [
        'midprice_returns', 'bid_ask_spread', 'trade_intensity',
        'order_book_imbalance', 'rolling_std_returns',
        'rolling_mean_spread', 'rolling_mean_imbalance'
    ]
    
    # Extract features in the correct order
    features = []
    for col in feature_cols:
        value = feature_data.get(col, 0.0)
        # Handle NaN/None
        if value is None or (isinstance(value, float) and np.isnan(value)):
            value = 0.0
        features.append(float(value))
    
    return np.array([features])


def make_prediction(model, features: np.ndarray) -> Dict:
    """Make prediction using the model."""
    try:
        # Validate features
        if features is None:
            logger.error("Features array is None")
            return None
        if len(features) == 0:
            logger.error("Features array is empty")
            return None
        
        # Get probability of positive class (volatility spike)
        proba = model.predict_proba(features)
        if proba is None:
            logger.error("Model returned None from predict_proba")
            return None
        
        # Handle numpy array shape
        try:
            if hasattr(proba, 'shape') and len(proba.shape) > 1:
                proba_array = proba[0]
            else:
                proba_array = proba
            
            if proba_array is None:
                logger.error("Probability array is None after extraction")
                return None
            
            # Convert to numpy array if needed and validate
            proba_array = np.array(proba_array)
            if len(proba_array) == 0:
                logger.error("Probability array is empty")
                return None
            
            # Extract score - prefer positive class probability
            if len(proba_array) > 1:
                raw_score = proba_array[1]
            else:
                raw_score = proba_array[0]
            
            # Convert to Python native type - handle numpy scalars
            try:
                if isinstance(raw_score, (np.integer, np.floating)):
                    score = float(raw_score.item())
                elif isinstance(raw_score, (int, float)):
                    score = float(raw_score)
                else:
                    score = float(raw_score)
            except (TypeError, ValueError) as e:
                logger.error(f"Cannot convert score to float: {raw_score} (type: {type(raw_score)}), error: {e}")
                return None
            
            # Check for None, NaN, or invalid values
            if score is None:
                logger.error("Score is None after conversion")
                return None
            
            try:
                if np.isnan(score) or np.isinf(score):
                    logger.error(f"Score is NaN or Inf: {score}")
                    return None
            except TypeError:
                # If score is not a number, np.isnan will fail
                logger.error(f"Score is not a valid number: {score} (type: {type(score)})")
                return None
            
        except (IndexError, TypeError, ValueError, AttributeError) as e:
            logger.error(f"Error extracting score from probability array: {e}, proba shape: {proba.shape if hasattr(proba, 'shape') else 'N/A'}")
            return None
        
        # Binary prediction (using 0.5 threshold, can be made configurable)
        try:
            prediction = 1 if score >= 0.5 else 0
        except TypeError as e:
            logger.error(f"Cannot compare score {score} (type: {type(score)}) with 0.5: {e}")
            return None
        
        return {
            'prediction': int(prediction),
            'score': score,
            'probability': score
        }
    except Exception as e:
        logger.error(f"Error making prediction: {e}", exc_info=True)
        return None


def main():
    global consumer, producer, model, running
    
    parser = argparse.ArgumentParser(description='Kafka Streaming Predictor')
    parser.add_argument('--topic_in', type=str, default='ticks.features',
                       help='Input Kafka topic (features)')
    parser.add_argument('--topic_out', type=str, default='ticks.predictions',
                       help='Output Kafka topic (predictions)')
    parser.add_argument('--config', type=str, default=None,
                       help='Path to config file')
    parser.add_argument('--batch_size', type=int, default=1,
                       help='Number of messages to process before committing')
    
    args = parser.parse_args()
    
    # Load configuration
    if args.config:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
    else:
        config = load_config()
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Load model from MLflow (with fallback to local)
    project_root = Path(__file__).parent.parent
    logger.info("Loading model...")
    model = load_model_from_mlflow(config, project_root)
    if model is None:
        logger.error("Failed to load model from both MLflow and local artifacts. Exiting.")
        return 1
    
    # Initialize Kafka consumer
    try:
        # Use a very large timeout value instead of None (Kafka library doesn't accept None)
        # sys.maxsize is effectively infinite for practical purposes
        consumer = KafkaConsumer(
            args.topic_in,
            bootstrap_servers=config['kafka']['bootstrap_servers'],
            auto_offset_reset='latest',  # Start from latest for real-time predictions
            enable_auto_commit=True,
            group_id=config['kafka']['consumer_group'] + '_predictor',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            consumer_timeout_ms=sys.maxsize  # Very large timeout - effectively infinite
        )
        logger.info(f"Connected to Kafka, consuming from {args.topic_in}")
    except Exception as e:
        logger.error(f"Failed to connect to Kafka: {e}")
        return 1
    
    # Initialize Kafka producer
    try:
        producer = KafkaProducer(
            bootstrap_servers=config['kafka']['bootstrap_servers'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        logger.info(f"Connected to Kafka producer, publishing to {args.topic_out}")
    except Exception as e:
        logger.error(f"Failed to create Kafka producer: {e}")
        return 1
    
    # Statistics
    message_count = 0
    prediction_count = 0
    error_count = 0
    start_time = time.time()
    
    try:
        logger.info("Starting prediction pipeline...")
        logger.info("Waiting for feature messages (will run continuously)...")
        
        for message in consumer:
            if not running:
                logger.info("Shutdown signal received, stopping...")
                break
            
            message_count += 1
            
            try:
                # Parse feature message
                feature_data = message.value
                
                # Transform features to model input
                features = transform_features(feature_data)
                if features is None:
                    logger.warning(f"Could not transform features from message {message_count}")
                    error_count += 1
                    continue
                
                # Make prediction
                prediction_result = make_prediction(model, features)
                if prediction_result is None:
                    logger.warning(f"Could not make prediction for message {message_count}")
                    error_count += 1
                    continue
                
                # Create prediction message
                prediction_msg = {
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'feature_timestamp': feature_data.get('timestamp'),
                    'product_id': feature_data.get('product_id', 'unknown'),
                    'prediction': prediction_result['prediction'],
                    'score': prediction_result['score'],
                    'probability': prediction_result['probability'],
                    'model_type': config.get('mlflow', {}).get('model_type', 'xgboost'),
                    'features': feature_data  # Include original features for reference
                }
                
                # Publish prediction
                try:
                    producer.send(args.topic_out, value=prediction_msg)
                    prediction_count += 1
                    
                    if prediction_count % 100 == 0:
                        logger.info(f"Processed {prediction_count} predictions (total messages: {message_count}, errors: {error_count})")
                except Exception as e:
                    logger.error(f"Error publishing prediction: {e}")
                    error_count += 1
                
            except Exception as e:
                logger.error(f"Error processing message {message_count}: {e}")
                error_count += 1
                continue
        
        # Flush producer (only reached if consumer loop exits)
        producer.flush()
        
        # Print statistics
        elapsed_time = time.time() - start_time
        logger.info("\n" + "=" * 60)
        logger.info("Prediction Pipeline Statistics")
        logger.info("=" * 60)
        logger.info(f"Total messages consumed: {message_count}")
        logger.info(f"Successful predictions: {prediction_count}")
        logger.info(f"Errors: {error_count}")
        logger.info(f"Elapsed time: {elapsed_time:.2f} seconds")
        if prediction_count > 0:
            logger.info(f"Average throughput: {prediction_count/elapsed_time:.2f} predictions/sec")
        logger.info("=" * 60)
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        import traceback
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        return 1
    finally:
        if consumer:
            consumer.close()
        if producer:
            producer.flush()
            producer.close()
    
    return 0


if __name__ == "__main__":
    exit(main())

