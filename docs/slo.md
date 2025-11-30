# Service Level Objectives (SLOs)

## Overview

This document defines the Service Level Objectives (SLOs) for the ML Prediction API. SLOs are aspirational targets that guide our reliability and performance goals.

## Primary SLO: Latency

### Target
- **P95 Latency ≤ 800ms** (aspirational target)

### Rationale
- 800ms provides a good balance between model accuracy and user experience
- Allows for complex feature computation and model inference
- Accounts for network overhead and system load

### Measurement
- Metric: `histogram_quantile(0.95, rate(predict_req_latency_bucket[5m]))`
- Window: 5-minute rolling window
- Unit: Seconds

### Compliance
- **Met**: P95 latency ≤ 0.8 seconds
- **Violated**: P95 latency > 0.8 seconds

### Monitoring
- Grafana dashboard shows P95 latency with SLO target line
- Alert configured when SLO is violated for >5 minutes

## Secondary SLOs

### Availability
- **Target**: 99.9% uptime (allows ~43 minutes downtime/month)
- **Measurement**: `/health` endpoint availability
- **Metric**: `up{job="ml-prediction-api"}`

### Error Rate
- **Target**: < 1% error rate
- **Measurement**: `rate(predict_req_errors_total[5m]) / rate(predict_req_tot[5m])`
- **Window**: 5-minute rolling window

### Throughput
- **Target**: Handle at least 100 requests/second
- **Measurement**: `rate(predict_req_tot[1m])`
- **Note**: This is a capacity target, not a hard requirement

## Data Freshness

### Target
- **Maximum staleness**: 5 minutes
- **Measurement**: Time since last successful prediction request
- **Metric**: `time() - predict_req_latency_sum / predict_req_latency_count`

### Rationale
- Ensures system is actively processing requests
- Detects if pipeline has stalled or stopped

## SLO Violation Response

### P95 Latency Violation
1. **Immediate**: Check system load and resource usage
2. **Short-term**: Review recent model deployments or configuration changes
3. **Long-term**: Consider model optimization or infrastructure scaling

### Availability Violation
1. **Immediate**: Check service health and logs
2. **Short-term**: Verify dependencies (Kafka, MLflow) are operational
3. **Long-term**: Review deployment process and error handling

### Error Rate Violation
1. **Immediate**: Review error logs and types
2. **Short-term**: Check for data drift or model degradation
3. **Long-term**: Review model retraining schedule

## Review and Updates

SLOs should be reviewed quarterly or when:
- System architecture changes significantly
- Traffic patterns change
- Model complexity increases
- Infrastructure is upgraded

## Notes

- These are **aspirational targets**, not hard SLAs
- SLOs may be adjusted based on operational experience
- Violations should trigger investigation, not immediate rollback
- Consider business impact when setting priorities for SLO violations

