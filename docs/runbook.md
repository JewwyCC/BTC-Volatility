# Operations Runbook

## Overview

This runbook provides operational procedures for the ML Prediction API system, including monitoring, troubleshooting, and incident response.

## System Components

- **API Server**: FastAPI application (`api_v1.py`)
- **Kafka**: Message broker for streaming data
- **MLflow**: Model registry and tracking
- **Prometheus**: Metrics collection
- **Grafana**: Metrics visualization

## Monitoring

### Key Metrics

1. **Latency** (P50, P95, P99)
   - Location: Grafana dashboard
   - Query: `histogram_quantile(0.95, rate(predict_req_latency_bucket[5m]))`
   - Alert threshold: P95 > 800ms for 5 minutes

2. **Error Rate**
   - Location: Grafana dashboard
   - Query: `rate(predict_req_errors_total[1m])`
   - Alert threshold: Error rate > 1% for 5 minutes

3. **Request Rate**
   - Location: Grafana dashboard
   - Query: `rate(predict_req_tot[1m])`
   - Normal range: 10-100 req/s

4. **Data Freshness**
   - Location: Grafana dashboard
   - Query: `time() - predict_req_latency_sum / predict_req_latency_count`
   - Alert threshold: > 5 minutes

### Accessing Dashboards

- **Grafana**: http://localhost:3000 (if running)
- **Prometheus**: http://localhost:9090 (if running)
- **MLflow**: http://localhost:5001
- **API Docs**: http://localhost:8000/docs

## Common Operations

### Starting the System

```bash
# 1. Start infrastructure
docker compose -f docker/compose.yaml up -d

# 2. Verify services
docker compose -f docker/compose.yaml ps

# 3. Start API server
python -m uvicorn api_v1:api --reload

# 4. Verify API health
curl http://localhost:8000/health
```

### Model Rollback

To rollback to baseline model:

```bash
# Set environment variable
export MODEL_VARIANT=baseline

# Restart API server
python -m uvicorn api_v1:api --reload
```

To use ML model (default):

```bash
export MODEL_VARIANT=ml
python -m uvicorn api_v1:api --reload
```

### Checking Model Version

```bash
curl http://localhost:8000/version
```

Expected response:
```json
{
  "model_var": "xgboost",
  "version": "abc12345",
  "loaded_from": "mlflow",
  "mlflow_run_id": "...",
  "mlflow_uri": "http://localhost:5001"
}
```

### Viewing Metrics

```bash
# Prometheus metrics endpoint
curl http://localhost:8000/metrics
```

## Troubleshooting

### High Latency (P95 > 800ms)

**Symptoms:**
- P95 latency exceeds 800ms
- Requests taking longer than expected

**Investigation:**
1. Check system resources:
   ```bash
   # CPU usage
   top
   
   # Memory usage
   free -h
   ```

2. Check API logs for errors or warnings

3. Review recent deployments or configuration changes

4. Check Kafka consumer lag (if applicable)

**Resolution:**
- Scale up API instances if CPU/memory constrained
- Review model complexity - consider model optimization
- Check for network issues
- Review feature computation time

### High Error Rate

**Symptoms:**
- Error rate > 1%
- Multiple 500/503 status codes

**Investigation:**
1. Check error types:
   ```bash
   # View error metrics
   curl http://localhost:8000/metrics | grep predict_req_errors
   ```

2. Check API logs:
   ```bash
   # Look for recent errors
   tail -f api.log | grep ERROR
   ```

3. Check model availability:
   ```bash
   curl http://localhost:8000/version
   ```

**Resolution:**
- If model not loaded: Check model path and MLflow connection
- If prediction errors: Check input data format
- If 503 errors: Verify model is loaded correctly
- Review data drift reports

### Service Unavailable

**Symptoms:**
- `/health` endpoint returns error
- No response from API

**Investigation:**
1. Check if API process is running:
   ```bash
   ps aux | grep uvicorn
   ```

2. Check port availability:
   ```bash
   lsof -i :8000
   ```

3. Check logs for crash messages

**Resolution:**
- Restart API server
- Check for port conflicts
- Verify dependencies (Kafka, MLflow) are accessible
- Review recent code changes

### Model Not Loading

**Symptoms:**
- `/version` shows `loaded_from: "none"`
- Predictions return 503

**Investigation:**
1. Check MLflow connection:
   ```bash
   curl http://localhost:5001/health
   ```

2. Check model files:
   ```bash
   ls -la models/artifacts/
   ```

3. Check configuration:
   ```bash
   cat config.yaml | grep mlflow
   ```

**Resolution:**
- Verify MLflow is running
- Check experiment name in config matches MLflow
- Verify model artifacts exist locally
- Check MODEL_VARIANT environment variable

### Data Drift Detected

**Symptoms:**
- Evidently report shows drift
- Model performance degradation

**Investigation:**
1. Review drift report:
   ```bash
   cat docs/drift_summary.md
   ```

2. Check feature distributions:
   ```bash
   python scripts/generate_evidently_report.py
   ```

**Resolution:**
- Review drift summary for specific features
- Consider model retraining if drift is significant
- Review data pipeline for changes
- Check for upstream data source changes

## Incident Response

### Severity Levels

**P0 - Critical**
- Service completely down
- All requests failing
- **Response**: Immediate escalation, all hands

**P1 - High**
- SLO violations (P95 > 800ms for >10 min)
- Error rate > 5%
- **Response**: On-call engineer, investigate within 15 min

**P2 - Medium**
- SLO violations (P95 > 800ms for <10 min)
- Error rate 1-5%
- **Response**: Investigate within 1 hour

**P3 - Low**
- Minor latency spikes
- Intermittent errors
- **Response**: Investigate during business hours

### Escalation

1. **First Responder**: On-call engineer
2. **Escalation**: Team lead if unresolved in 30 min
3. **Critical**: All hands if service down

## Maintenance

### Regular Tasks

1. **Weekly**: Review SLO compliance
2. **Monthly**: Review drift reports
3. **Quarterly**: Review and update SLOs
4. **As needed**: Model retraining based on drift

### Model Updates

1. Train new model: `python models/train.py --model_type xgboost`
2. Verify model performance in MLflow
3. Update config if needed
4. Restart API to load new model (if using 'latest')

### Log Rotation

```bash
# Rotate logs if using file logging
logrotate -f /etc/logrotate.d/ml-api
```

## Useful Commands

```bash
# Check API health
curl http://localhost:8000/health

# Check model version
curl http://localhost:8000/version

# View metrics
curl http://localhost:8000/metrics

# Test prediction
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"rows": [{"ret_mean": 0.001, "ret_std": 0.01, "n": 100}]}'

# Check Kafka topics
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092

# Check MLflow experiments
mlflow experiments list --tracking-uri http://localhost:5001
```

## Contact

- **On-call**: [Contact information]
- **Slack**: #ml-prediction-api
- **Documentation**: See `docs/` directory

