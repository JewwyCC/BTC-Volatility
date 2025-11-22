from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
import prometheus_client
from prometheus_client import Counter
from prometheus_client import Histogram
import joblib
import os
from datetime import datetime, timezone
from pydantic import BaseModel

model_var = "xgb"
model_version = "v1"
model = joblib.load("/models/artifacts/xgb_model.pkl")

count = Counter("predict_req_tot")
latency = Histogram("predict_req_latency")

api = FastAPI()

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
