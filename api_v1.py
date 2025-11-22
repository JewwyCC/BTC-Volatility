from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
import prometheus_client
from prometheus_client import Counter
from prometheus_client import Histogram
import logging
import joblib
import os
from datetime import datetime, timezone
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException

logger = logging.getLogger(__name__)

model_var = "xgb"
model_version = "v1"
# Get the directory where this script is located
script_dir = os.path.dirname(__file__)
model_path = os.path.join(script_dir, "models", "artifacts", "xgb_model.pkl")

model = None
try:
    model = joblib.load(model_path)
    logger.info("Loaded model from %s", model_path)
except Exception as e:
    # Do NOT crash the whole API if model/xgboost cannot be loaded
    logger.warning(
        "Could not load model from %s. Predict endpoint will be disabled. Error: %s",
        model_path,
        e,
    )
    model = None


count = Counter("predict_req_tot", "Total number of prediction requests")
latency = Histogram("predict_req_latency", "Latency of prediction requests in seconds")

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
            "/redoc": "GET - Alternative API documentation (ReDoc)"
        }
    }

class Row(BaseModel):
    ret_mean : float
    ret_std : float
    n : int

class Payload(BaseModel):
    rows : list[Row]

@api.get("/health")
def health():
    return {"status" : "ok"}

@api.get("/version")
def version():
    return {"model_var" : model_var, "version" : model_version}

@api.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return prometheus_client.generate_latest()


@api.post("/predict")
def predict(payload : Payload):
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded on this server instance.",
        )
    
    count.inc()

    with latency.time():
        X = [[row.ret_mean, row.ret_std, row.n] for row in payload.rows]
        scores = model.predict_proba(X)[:, 1].tolist()

    return {
        "scores" : scores,
        "model_var" : model_var,
        "version" : model_version,
        "time" : datetime.now(timezone.utc).isoformat()
    }
