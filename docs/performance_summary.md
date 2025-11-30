# Performance Summary

**Date:** 2025-11-29  
**System:** ML Prediction API - Real-Time Crypto Volatility Detection

## Executive Summary

This document summarizes the performance metrics for the ML Prediction API system, including latency, uptime, and model performance (PR-AUC) compared to baseline.

## Model Performance: PR-AUC vs Baseline

### Primary Metric: PR-AUC (Precision-Recall Area Under Curve)

PR-AUC is the primary evaluation metric for this imbalanced classification problem.

| Model | Test PR-AUC | Improvement vs Baseline |
|-------|-------------|------------------------|
| **Baseline (Z-Score Rule)** | 0.1023 | - |
| **ML Model (Logistic Regression)** | 0.1668 | +63% |
| **ML Model (XGBoost)** ⭐ | **0.4678** | **+357%** |

**Key Finding:** XGBoost model achieves **4.6x improvement** in PR-AUC compared to baseline, making it the recommended model for production.

### Detailed Model Comparison

#### Baseline Model
- **Test PR-AUC:** 0.1023
- **Test ROC-AUC:** 0.2259
- **Test F1 Score:** 0.0000
- **Test Precision:** 0.0000
- **Test Recall:** 0.0000
- **Status:** ❌ Poor performance, not recommended

#### ML Model (XGBoost) - Production Model
- **Test PR-AUC:** 0.4678 ⬆️ **357% improvement over baseline**
- **Test ROC-AUC:** 0.9174
- **Test F1 Score:** 0.4848
- **Test Precision:** 0.3220
- **Test Recall:** 0.9806 (catches 98% of volatility spikes)
- **Status:** ✅ **Excellent performance, recommended for production**

## Latency Performance

### SLO Target
- **P95 Latency ≤ 800ms** (aspirational target)

### Load Test Results

**Test Configuration:**
- Endpoint: `/predict`
- Requests: 100 concurrent (burst)
- Payload: Single row prediction

**Results:**
- **P50 Latency:** ~17.5ms
- **P95 Latency:** ~29.1ms
- **P99 Latency:** ~33.9ms
- **Max Latency:** ~33.9ms
- **Mean Latency:** ~18.1ms
- **Throughput:** ~1,712 req/s

**Status:** ✅ **P95 latency (29.1ms) is well below SLO target (800ms)**

**Note:** These results are from load testing with API not under full production load. Actual production latency may vary based on:
- System load
- Model complexity
- Network conditions
- Concurrent requests

### Latency Distribution

The system demonstrates excellent latency characteristics:
- **Sub-20ms** for 50% of requests
- **Sub-30ms** for 95% of requests
- **Sub-35ms** for 99% of requests

This performance is well within the aspirational SLO target of 800ms P95 latency.

## Uptime & Availability

### Target SLO
- **99.9% uptime** (allows ~43 minutes downtime/month)

### System Components

**Infrastructure:**
- Docker Compose orchestration
- Health checks for all services
- Graceful shutdown handling
- Automatic service recovery

**Reliability Features:**
- ✅ Graceful shutdown on SIGTERM/SIGINT
- ✅ Health check endpoints (`/health`)
- ✅ Service dependency management
- ✅ Error tracking and monitoring
- ✅ Model rollback capability

### Availability Metrics

**Service Health:**
- API health endpoint: `GET /health` → `{"status": "ok"}`
- Service dependencies: Kafka, MLflow with health checks
- Model loading: Fallback mechanism (MLflow → local artifacts)

**Monitoring:**
- Prometheus metrics exposed
- Error rates tracked
- Service status monitored
- Model version tracking

**Note:** Actual uptime metrics would require production deployment and monitoring over time. The system is designed for high availability with:
- Health checks
- Graceful error handling
- Service recovery mechanisms
- Model fallback strategies

## System Performance Summary

### Model Performance ✅
- **PR-AUC:** 0.4678 (XGBoost) vs 0.1023 (Baseline) = **4.6x improvement**
- **F1 Score:** 0.4848 vs 0.0000 = **Significant improvement**
- **Recall:** 98.06% (catches nearly all volatility spikes)

### Latency Performance ✅
- **P95 Latency:** 29.1ms (well below 800ms target)
- **P99 Latency:** 33.9ms
- **Throughput:** 1,712 req/s

### Availability ✅
- **Target:** 99.9% uptime
- **Features:** Health checks, graceful shutdown, error recovery
- **Monitoring:** Prometheus metrics, service status tracking

## Recommendations

1. **Model Selection:** Use XGBoost model for production (4.6x PR-AUC improvement)
2. **Latency:** Current performance exceeds SLO targets significantly
3. **Monitoring:** Continue tracking latency, error rates, and availability
4. **Scaling:** System can handle high throughput (1,700+ req/s in testing)

## Notes

- Performance metrics based on test environment
- Production metrics may vary based on load and infrastructure
- Regular monitoring recommended to track performance over time
- Model performance based on test set evaluation (20% of data, time-based split)

---

**Data Sources:**
- Model evaluation: `reports/model_eval.md`
- Load testing: `scripts/load_test.py`
- System architecture: `docs/project_status.md`

