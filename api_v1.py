import logging
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import yaml
import joblib
import numpy as np
import prometheus_client
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, Gauge

# MLflow imports
try:
    import mlflow
    import mlflow.sklearn
    import mlflow.xgboost

    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    logging.warning("MLflow not available, will fall back to local model loading")

logger = logging.getLogger(__name__)

# Configuration
script_dir = Path(__file__).parent
config_path = script_dir / "config.yaml"

# Load configuration
config = {}
mlflow_config = {}
model_config = {}
try:
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    mlflow_config = config.get("mlflow", {})
    model_config = config.get("model", {})
except Exception as e:
    logger.warning(f"Could not load config.yaml: {e}. Using defaults.")

# Model loading configuration
# Support MODEL_VARIANT environment variable for rollback (ml|baseline)
model_variant = os.getenv("MODEL_VARIANT", "ml").lower()  # 'ml' or 'baseline'
if model_variant == "baseline":
    # Use baseline model
    model_type = "logistic"  # Baseline is logistic regression
    logger.info("MODEL_VARIANT=baseline: Using baseline model")
else:
    model_type = mlflow_config.get("model_type", "xgboost")
    logger.info(f"MODEL_VARIANT=ml: Using ML model ({model_type})")

# Determine MLflow URI - use service name if running in Docker, localhost otherwise
# Check if we're in Docker by looking for /app (Dockerfile sets WORKDIR to /app)
default_mlflow_uri = (
    "http://mlflow:5000" if Path("/app").exists() else "http://localhost:5001"
)
mlflow_uri = mlflow_config.get("tracking_uri", default_mlflow_uri)
experiment_name = mlflow_config.get("experiment_name", "volatility_detection")
model_source = mlflow_config.get(
    "model_source", "latest"
)  # 'latest', 'run_id', or 'local'
run_id = mlflow_config.get("run_id")
use_calibrated = mlflow_config.get("use_calibrated", False)

# Fallback local model path (determined by model_variant)
if model_variant == "baseline":
    model_path = script_dir / "models" / "artifacts" / "logistic_model.pkl"
else:
    model_path = script_dir / "models" / "artifacts" / "xgb_model.pkl"

# Model state
model = None
model_var = model_type
model_version = "unknown"
mlflow_run_id = None
model_loaded_from = "none"


def load_model_from_mlflow() -> Optional[tuple]:
    """Load model from MLflow. Returns (model, run_id) tuple or None."""
    if not MLFLOW_AVAILABLE:
        logger.warning("MLflow not available, cannot load from MLflow")
        return None

    try:
        mlflow.set_tracking_uri(mlflow_uri)
        logger.info(f"Connecting to MLflow at {mlflow_uri}")

        # Get experiment
        try:
            experiment = mlflow.get_experiment_by_name(experiment_name)
            if experiment is None:
                logger.warning(f"Experiment '{experiment_name}' not found in MLflow")
                return None
            experiment_id = experiment.experiment_id
        except Exception as e:
            logger.warning(f"Could not get experiment '{experiment_name}': {e}")
            return None

        # Determine which run to load
        target_run_id = None
        if model_source == "run_id" and run_id:
            target_run_id = run_id
            logger.info(f"Loading model from specified run_id: {target_run_id}")
        elif model_source == "latest":
            # Get latest run from experiment
            runs = mlflow.search_runs(
                experiment_ids=[experiment_id],
                order_by=["start_time DESC"],
                max_results=1,
            )
            if runs.empty:
                logger.warning(f"No runs found in experiment '{experiment_name}'")
                return None
            target_run_id = runs.iloc[0]["run_id"]
            logger.info(f"Loading latest model from run_id: {target_run_id}")
        else:
            logger.warning(f"Invalid model_source: {model_source}")
            return None

        # Load model based on type
        loaded_model = None
        if model_type == "xgboost":
            try:
                loaded_model = mlflow.xgboost.load_model(f"runs:/{target_run_id}/model")
                logger.info(f"Loaded XGBoost model from MLflow run {target_run_id}")
            except Exception as e:
                logger.warning(f"Could not load XGBoost model from MLflow: {e}")
                return None
        else:
            try:
                loaded_model = mlflow.sklearn.load_model(f"runs:/{target_run_id}/model")
                logger.info(f"Loaded sklearn model from MLflow run {target_run_id}")
            except Exception as e:
                logger.warning(f"Could not load sklearn model from MLflow: {e}")
                return None

        return (loaded_model, target_run_id)

    except Exception as e:
        logger.warning(f"Error loading model from MLflow: {e}")
        return None


def load_model_from_local() -> Optional[object]:
    """Load model from local artifacts directory."""
    try:
        # Try joblib first, fallback to pickle
        try:
            model = joblib.load(model_path)
        except FileNotFoundError:
            raise  # Re-raise to be caught by outer handler
        except Exception:
            import pickle

            with open(model_path, "rb") as f:
                model = pickle.load(f)
        logger.info(f"Loaded model from local path: {model_path}")
        return model
    except FileNotFoundError:
        logger.warning(f"Model file not found at {model_path}")
        return None
    except Exception as e:
        logger.warning(f"Could not load model from {model_path}: {e}")
        return None


# Attempt to load model
if model_source in ["latest", "run_id"] and MLFLOW_AVAILABLE:
    result = load_model_from_mlflow()
    if result is not None and isinstance(result, tuple):
        model, mlflow_run_id = result
        model_loaded_from = "mlflow"
        model_version = mlflow_run_id[:8] if mlflow_run_id else "unknown"
    else:
        logger.warning("Failed to load from MLflow, falling back to local artifacts")
        model = load_model_from_local()
        if model is not None:
            model_loaded_from = "local"
            model_version = "local"
else:
    # Load from local artifacts
    model = load_model_from_local()
    if model is not None:
        model_loaded_from = "local"
        model_version = "local"

if model is None:
    logger.error(
        "Could not load model from any source. Predict endpoint will be disabled."
    )

# Prometheus metrics
count = Counter("predict_req_tot", "Total number of prediction requests")
latency = Histogram(
    "predict_req_latency",
    "Latency of prediction requests in seconds",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0],
)
error_count = Counter(
    "predict_req_errors",
    "Total number of prediction errors",
    ["status_code", "error_type"],
)
request_count = Counter(
    "predict_req_by_status", "Total requests by HTTP status code", ["status_code"]
)
model_version_gauge = Gauge(
    "model_version_info",
    "Model version information",
    ["model_var", "version", "loaded_from"],
)

# Set model version gauge
if model is not None:
    model_version_gauge.labels(
        model_var=model_var, version=model_version, loaded_from=model_loaded_from
    ).set(1)

api = FastAPI(title="ML Prediction API", version="1.0.0")


@api.get("/")
async def root():
    return {
        "message": "ML Prediction API",
        "model": model_var,
        "version": model_version,
        "endpoints": {
            "/health": "GET - Health check endpoint",
            "/version": "GET - Get model version information",
            "/metrics": "GET - Prometheus metrics",
            "/predict": "POST - Make predictions (requires JSON payload)",
            "/docs": "GET - Interactive API documentation (Swagger UI)",
            "/redoc": "GET - Alternative API documentation (ReDoc)",
        },
    }


class Row(BaseModel):
    ret_mean: float
    ret_std: float
    n: int


class Payload(BaseModel):
    rows: list[Row]


def transform_to_model_features(ret_mean: float, ret_std: float, n: int) -> list:
    """
    Transform API input (3 features) to model input (7 features).

    Model expects (in order):
    1. midprice_returns
    2. bid_ask_spread
    3. trade_intensity
    4. order_book_imbalance
    5. rolling_std_returns
    6. rolling_mean_spread
    7. rolling_mean_imbalance

    API provides:
    - ret_mean: mean return (maps to midprice_returns)
    - ret_std: standard deviation (maps to rolling_std_returns)
    - n: number of observations (maps to trade_intensity)

    For missing features, use reasonable defaults based on typical BTC-USD market conditions.
    Defaults are based on training data statistics.
    """
    # Direct mappings
    midprice_returns = float(ret_mean)
    rolling_std_returns = float(ret_std)
    # Trade intensity: convert n (observations in window) to ticks per second
    # Assuming 60-second window, n observations = n/60 ticks per second
    trade_intensity = float(n) / 60.0 if n > 0 else 0.0

    # Default values for missing features (based on typical BTC-USD market data)
    # These defaults are derived from training data statistics
    # Typical bid-ask spread: ~0.0001 to 0.001 (0.01% to 0.1%)
    # Use a small default spread, scaled by volatility
    bid_ask_spread = max(0.0001, abs(ret_mean) * 0.02) if ret_mean != 0 else 0.0001

    # Order book imbalance: typically ranges from -1 to 1, default to neutral (0)
    order_book_imbalance = 0.0

    # Rolling means: use current values as defaults (simplified)
    rolling_mean_spread = bid_ask_spread
    rolling_mean_imbalance = 0.0

    # Return in the exact order expected by the model
    return [
        midprice_returns,  # 0: midprice_returns
        bid_ask_spread,  # 1: bid_ask_spread
        trade_intensity,  # 2: trade_intensity
        order_book_imbalance,  # 3: order_book_imbalance
        rolling_std_returns,  # 4: rolling_std_returns
        rolling_mean_spread,  # 5: rolling_mean_spread
        rolling_mean_imbalance,  # 6: rolling_mean_imbalance
    ]


@api.get("/health")
def health():
    return {"status": "ok"}


@api.get("/version")
def version():
    import subprocess

    # Get git SHA
    try:
        sha = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=script_dir,
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        sha = model_version[:7] if len(model_version) >= 7 else "unknown"

    return {"model": model_var, "sha": sha}


@api.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return prometheus_client.generate_latest()


@api.post("/predict")
def predict(payload: Payload):
    if model is None:
        error_count.labels(status_code="503", error_type="model_not_loaded").inc()
        request_count.labels(status_code="503").inc()
        raise HTTPException(
            status_code=503,
            detail="Model not loaded on this server instance.",
        )

    count.inc()
    request_count.labels(status_code="200").inc()

    try:
        with latency.time():
            # Transform API input (3 features) to model input (7 features)
            X = [
                transform_to_model_features(row.ret_mean, row.ret_std, row.n)
                for row in payload.rows
            ]
            X_array = np.array(X)
            scores = model.predict_proba(X_array)[:, 1].tolist()

        return {
            "scores": scores,
            "model_variant": model_variant,
            "version": model_version,
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    except Exception as e:
        error_count.labels(status_code="500", error_type=type(e).__name__).inc()
        request_count.labels(status_code="500").inc()
        logger.error(f"Prediction error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(e)}",
        )
