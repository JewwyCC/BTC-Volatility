# Demo Checklist: 8-Minute System Demonstration

## Overview
This checklist ensures all required demo components are covered in the 8-minute video.

## Demo Structure (8 minutes)

### 1. Startup (1-2 minutes)
- [ ] Show repository structure
- [ ] Run `docker compose up -d`
- [ ] Verify services start: Kafka, MLflow, API
- [ ] Check health endpoints: `curl http://localhost:8000/health`
- [ ] Show version: `curl http://localhost:8000/version`

### 2. Prediction (2-3 minutes)
- [ ] Make prediction request:
  ```bash
  curl -X POST http://localhost:8000/predict \
    -H "Content-Type: application/json" \
    -d '{"rows": [{"ret_mean": 0.05, "ret_std": 0.01, "n": 50}]}'
  ```
- [ ] Show response format matches API contract
- [ ] Make multiple predictions to show consistency
- [ ] Show metrics endpoint: `curl http://localhost:8000/metrics`

### 3. Failure Recovery (2-3 minutes)
- [ ] **Option A: Kafka Failure**
  - Stop Kafka: `docker stop kafka`
  - Show API still responds (graceful degradation)
  - Restart Kafka: `docker start kafka`
  - Show recovery
  
- [ ] **Option B: API Error Simulation**
  - Trigger 500 error (e.g., invalid input)
  - Show error handling
  - Show error metrics
  - Make successful request after

- [ ] **Option C: Service Restart**
  - Restart API: `docker restart ml-prediction-api`
  - Show health check recovery
  - Verify predictions work after restart

### 4. Rollback (1-2 minutes)
- [ ] Show current model: `curl http://localhost:8000/version`
- [ ] Set `MODEL_VARIANT=baseline` in docker-compose or environment
- [ ] Restart API service
- [ ] Verify rollback: `curl http://localhost:8000/version`
- [ ] Make prediction with baseline model
- [ ] Show response includes `model_variant: "baseline"`

## Key Points to Highlight

### Architecture
- [ ] One-command startup (`docker compose up -d`)
- [ ] Service health checks
- [ ] Network isolation
- [ ] Volume persistence

### API Contract Compliance
- [ ] `/predict` returns: `scores`, `model_variant`, `version`, `ts`
- [ ] `/version` returns: `model`, `sha`
- [ ] `/health` returns: `{"status": "ok"}`
- [ ] `/metrics` returns Prometheus format

### Reliability Features
- [ ] Graceful shutdown handling
- [ ] Error tracking and metrics
- [ ] Health checks
- [ ] Service dependencies

### Monitoring
- [ ] Prometheus metrics exposed
- [ ] Error rates tracked
- [ ] Latency metrics available
- [ ] Model version tracking

### Rollback Capability
- [ ] MODEL_VARIANT environment variable
- [ ] Quick model switching
- [ ] No code changes required

## Demo Script Template

```
[0:00-0:30] Introduction
- Project overview
- System architecture (show diagram if available)

[0:30-2:00] Startup
- Show docker-compose.yaml
- Run docker compose up -d
- Verify services
- Check health endpoints

[2:00-4:30] Prediction
- Make prediction requests
- Show response format
- Demonstrate multiple predictions
- Show metrics

[4:30-6:30] Failure Recovery
- Simulate failure (choose one)
- Show error handling
- Demonstrate recovery
- Verify system returns to normal

[6:30-8:00] Rollback
- Show current model version
- Demonstrate rollback procedure
- Verify rollback success
- Make prediction with baseline model

[8:00] Wrap-up
- Summary of key features
- System capabilities
```

## Pre-Demo Preparation

### Environment Setup
- [ ] Docker and Docker Compose installed
- [ ] All services can start successfully
- [ ] Models are available in `models/artifacts/`
- [ ] Config files are correct

### Test Run
- [ ] Run through entire demo once
- [ ] Verify all commands work
- [ ] Check response formats
- [ ] Test failure scenarios
- [ ] Test rollback procedure

### Recording Setup
- [ ] Screen recording software ready
- [ ] Terminal with readable font
- [ ] Browser ready for Grafana (optional)
- [ ] Audio clear (if narrating)

## Post-Demo

- [ ] Upload to YouTube (unlisted)
- [ ] Add link to README
- [ ] Verify video is accessible
- [ ] Update submission documentation

## Tips

1. **Keep it concise**: 8 minutes is tight, focus on key features
2. **Show, don't tell**: Let the commands speak for themselves
3. **Practice**: Run through the demo at least once before recording
4. **Have backup**: If something fails, have a plan B
5. **Highlight key features**: Emphasize one-command startup, rollback, monitoring

## Common Issues & Solutions

### Services won't start
- Check ports aren't in use
- Verify Docker has enough resources
- Check docker-compose.yaml syntax

### API returns 503
- Verify model files exist
- Check MODEL_VARIANT environment variable
- Review API logs

### Rollback doesn't work
- Ensure MODEL_VARIANT is set before API starts
- Restart API after changing environment variable
- Check model files exist for both variants

