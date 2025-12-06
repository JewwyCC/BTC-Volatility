#!/bin/sh
# Custom entrypoint for MLflow to force binding to 0.0.0.0

set -e

# Create directories
mkdir -p /mlflow/mlruns /mlflow/artifacts
chmod -R 777 /mlflow/mlruns /mlflow/artifacts 2>/dev/null || true

# Override gunicorn bind address by setting environment variable
export GUNICORN_CMD_ARGS="--bind=0.0.0.0:5000 --workers=2"

# Run MLflow server with explicit host binding
exec mlflow server \
  --host 0.0.0.0 \
  --port 5000 \
  --backend-store-uri file:///mlflow/mlruns \
  --default-artifact-root /mlflow/artifacts

