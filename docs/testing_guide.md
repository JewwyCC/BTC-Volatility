# System Testing Guide

This guide provides comprehensive instructions for testing the system to ensure it runs perfectly.

## Quick Test

Run the automated test script:

```bash
python scripts/test_system.py
```

This will test:
- Docker Compose availability
- Services running
- All API endpoints
- API contract compliance
- Error handling
- Multiple predictions

## Manual Testing Steps

### 1. Start the System

```bash
# Start all services
docker compose up -d

# Wait for services to be ready (30-60 seconds)
docker compose ps

# Check service health
docker compose logs api | tail -20
```

### 2. Test Health Endpoint

```bash
curl http://localhost:8000/health
```

**Expected:** `{"status": "ok"}`

### 3. Test Version Endpoint

```bash
curl http://localhost:8000/version
```

**Expected:** 
```json
{
  "model": "xgboost",
  "sha": "884967e"
}
```

### 4. Test Predict Endpoint (API Contract)

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "rows": [
      {"ret_mean": 0.05, "ret_std": 0.01, "n": 50}
    ]
  }'
```

**Expected:**
```json
{
  "scores": [0.74],
  "model_variant": "ml",
  "version": "local",
  "ts": "2025-11-29T20:52:18Z"
}
```

**Verify:**
- ✅ `scores` is an array
- ✅ `model_variant` is a string ("ml" or "baseline")
- ✅ `version` is a string
- ✅ `ts` is in format `YYYY-MM-DDTHH:MM:SSZ`

### 5. Test Metrics Endpoint

```bash
curl http://localhost:8000/metrics
```

**Expected:** Prometheus-format metrics including:
- `predict_req_tot`
- `predict_req_latency_bucket`
- `predict_req_errors_total`
- `predict_req_by_status_total`

### 6. Test Error Handling

```bash
# Invalid payload
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"invalid": "payload"}'
```

**Expected:** 400 or 422 status code with error message

### 7. Test Multiple Predictions

```bash
# Run 5 predictions
for i in {1..5}; do
  echo "Prediction $i:"
  curl -X POST http://localhost:8000/predict \
    -H "Content-Type: application/json" \
    -d '{"rows": [{"ret_mean": 0.05, "ret_std": 0.01, "n": 50}]}'
  echo ""
  sleep 1
done
```

**Verify:** All predictions return consistent format

### 8. Test Model Rollback

```bash
# Check current model
curl http://localhost:8000/version

# Stop API
docker stop ml-prediction-api

# Edit docker-compose.yaml to set MODEL_VARIANT=baseline
# Or set environment variable
export MODEL_VARIANT=baseline

# Restart API
docker start ml-prediction-api
# Or: docker compose up -d api

# Wait for restart
sleep 5

# Verify rollback
curl http://localhost:8000/version
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"rows": [{"ret_mean": 0.05, "ret_std": 0.01, "n": 50}]}'
```

**Expected:** 
- Version shows baseline model
- Predict response shows `"model_variant": "baseline"`

### 9. Test Failure Recovery

```bash
# Stop Kafka
docker stop kafka

# Try prediction (should handle gracefully)
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"rows": [{"ret_mean": 0.05, "ret_std": 0.01, "n": 50}]}'

# Restart Kafka
docker start kafka

# Wait for recovery
sleep 10

# Verify system recovered
curl http://localhost:8000/health
```

### 10. Test Load

```bash
# Run load test
python scripts/load_test.py
```

**Expected:** 
- 100 concurrent requests
- P95 latency < 800ms
- Success rate > 99%

## Service-Specific Tests

### Kafka

```bash
# Check Kafka is running
docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092

# List topics
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092
```

### MLflow

```bash
# Check MLflow health
curl http://localhost:5001/health

# List experiments (if MLflow UI available)
open http://localhost:5001
```

### API Service

```bash
# Check API logs
docker logs ml-prediction-api

# Check API health
docker exec ml-prediction-api curl -f http://localhost:8000/health
```

## Integration Test

Test the full pipeline:

```bash
# 1. Start services
docker compose up -d

# 2. Wait for readiness
sleep 30

# 3. Run automated test
python scripts/test_system.py

# 4. Run load test
python scripts/load_test.py

# 5. Check metrics
curl http://localhost:8000/metrics | grep predict_req
```

## Troubleshooting

### Services Won't Start

```bash
# Check ports
lsof -i :8000
lsof -i :9092
lsof -i :5001

# Check Docker resources
docker system df
docker system prune  # If needed

# View logs
docker compose logs
```

### API Returns 503

```bash
# Check model files
ls -la models/artifacts/

# Check API logs
docker logs ml-prediction-api

# Verify MODEL_VARIANT
docker exec ml-prediction-api env | grep MODEL_VARIANT
```

### Predictions Fail

```bash
# Check request format
curl -v -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"rows": [{"ret_mean": 0.05, "ret_std": 0.01, "n": 50}]}'

# Check error response
# Look for error details in response
```

## Expected Test Results

### All Tests Passing

```
✓ Docker Compose available
✓ Service 'kafka' is running
✓ Service 'mlflow' is running
✓ Service 'ml-prediction-api' is running
✓ Service is ready
✓ /health returns correct response
✓ /version returns: model=xgboost, sha=884967e
✓ /metrics returns Prometheus format
✓ /predict returns correct format
✓ Error handling works
✓ All 5 predictions consistent

Total: 11/11 tests passed
✅ All tests passed! System is ready.
```

## Pre-Demo Testing

Before recording the demo video:

1. **Run full test suite:**
   ```bash
   python scripts/test_system.py
   ```

2. **Verify all endpoints:**
   - Health, Version, Predict, Metrics

3. **Test rollback:**
   - Switch between ml and baseline models

4. **Test failure recovery:**
   - Restart services
   - Verify recovery

5. **Load test:**
   ```bash
   python scripts/load_test.py
   ```

6. **Check metrics:**
   ```bash
   curl http://localhost:8000/metrics
   ```

## Continuous Testing

For development, run tests after changes:

```bash
# Quick health check
curl http://localhost:8000/health

# Full test
python scripts/test_system.py

# Load test
python scripts/load_test.py
```

## Notes

- Tests assume services are running on default ports
- Some tests may take 30-60 seconds for services to be ready
- Load test requires API to be running
- Model rollback test requires restarting the API service

