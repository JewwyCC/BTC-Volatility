# Testing Troubleshooting Guide

## Common Issues

### Services Show as Not Running in Test

**Symptom:** Test says services aren't running, but Docker Dashboard shows them running.

**Cause:** The test checks for specific container names. Services might be running with different names or started differently.

**Solution:**

1. **Check actual container names:**
   ```bash
   docker ps --format "{{.Names}}"
   ```

2. **If using docker-compose.yaml:**
   ```bash
   # Start all services
   docker compose up -d
   
   # Check what's running
   docker compose ps
   ```

3. **If containers are running but test fails:**
   - The test now checks containers directly, so this should work
   - If API isn't running, start it:
     ```bash
     # Option 1: Via docker compose
     docker compose up -d api
     
     # Option 2: Run separately (if not using docker)
     python -m uvicorn api_v1:api --reload
     ```

### API Service Not Running

**Symptom:** Test shows API is not running.

**Solutions:**

1. **Start via Docker Compose:**
   ```bash
   docker compose up -d api
   ```

2. **Or run separately (recommended for development):**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python -m uvicorn api_v1:api --reload
   ```

3. **Check if API container exists:**
   ```bash
   docker ps -a | grep api
   ```

4. **If container doesn't exist, build it:**
   ```bash
   docker compose build api
   docker compose up -d api
   ```

### API Not Responding

**Symptom:** API container is running but endpoints don't respond.

**Check:**

1. **Verify API is listening:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Check API logs:**
   ```bash
   docker logs ml-prediction-api
   # OR if running separately, check terminal output
   ```

3. **Check port is available:**
   ```bash
   lsof -i :8000
   ```

4. **Verify model is loaded:**
   ```bash
   curl http://localhost:8000/version
   ```

### Docker Compose Shows No Services

**Symptom:** `docker compose ps` shows empty.

**Possible causes:**

1. **Services started with different compose file:**
   ```bash
   # Check which compose file was used
   docker ps --format "{{.Names}}\t{{.Label \"com.docker.compose.project\"}}"
   ```

2. **Services started manually:**
   ```bash
   # Check all running containers
   docker ps
   ```

3. **Services in different directory:**
   - Make sure you're in the project root
   - Check if there's a docker-compose.yaml in current directory

### Test Script Can't Connect to API

**Symptom:** All tests fail with connection errors.

**Solutions:**

1. **Verify API is running:**
   ```bash
   # Check container
   docker ps | grep api
   
   # Check process (if running separately)
   ps aux | grep uvicorn
   ```

2. **Test connection manually:**
   ```bash
   curl http://localhost:8000/health
   ```

3. **Check firewall/network:**
   - Ensure port 8000 is not blocked
   - Try `curl http://127.0.0.1:8000/health` instead

4. **Check API logs for errors:**
   ```bash
   docker logs ml-prediction-api
   ```

## Quick Fixes

### Restart Everything

```bash
# Stop all
docker compose down

# Start all
docker compose up -d

# Wait 30 seconds
sleep 30

# Run test
python scripts/test_system.py
```

### Start API Separately (If Docker Issues)

```bash
# In one terminal
python -m uvicorn api_v1:api --reload

# In another terminal, run test
python scripts/test_system.py
```

### Check Service Status

```bash
# All containers
docker ps

# Specific service
docker ps | grep -E "(kafka|mlflow|api)"

# Service health
docker compose ps
```

## Test Script Improvements

The test script now:
- ✅ Checks containers directly (more reliable)
- ✅ Provides helpful messages if services aren't running
- ✅ Suggests how to start missing services
- ✅ Continues testing even if some services are missing

## Expected Behavior

### If All Services Running:

```
✓ Service 'kafka' is running (container: kafka)
✓ Service 'mlflow' is running (container: mlflow)
✓ Service 'api' is running (container: ml-prediction-api)
✓ Service is ready
✓ /health returns correct response
...
```

### If API Not Running:

```
✓ Service 'kafka' is running (container: kafka)
✓ Service 'mlflow' is running (container: mlflow)
⚠ Service 'api' is not running
  Note: API can be run separately with: python -m uvicorn api_v1:api --reload
⚠ Service did not become ready in time
  Start API with: docker compose up -d api
  OR run separately: python -m uvicorn api_v1:api --reload
```

## Manual Verification

If automated test fails, verify manually:

```bash
# 1. Check containers
docker ps

# 2. Test health
curl http://localhost:8000/health

# 3. Test version
curl http://localhost:8000/version

# 4. Test predict
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"rows": [{"ret_mean": 0.05, "ret_std": 0.01, "n": 50}]}'
```

If these work, the system is fine - the test script just needs adjustment.

