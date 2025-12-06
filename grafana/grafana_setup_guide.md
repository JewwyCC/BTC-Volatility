# Grafana Dashboard Setup Guide

This guide will help you set up and view the Grafana dashboard for taking screenshots.

## Quick Start

1. **Start all services:**
   ```bash
   docker compose up -d
   ```

2. **Wait for services to be healthy** (30-60 seconds):
   ```bash
   docker compose ps
   ```

3. **Generate some traffic** (so there are metrics to display):
   ```bash
   # Run load test to generate metrics
   python tests/load_test.py
   ```

4. **Access Grafana:**
   - URL: http://localhost:3000
   - Username: `admin`
   - Password: `admin`

5. **Import the dashboard:**
   - Go to Dashboards → Import
   - Click "Upload JSON file"
   - Select `grafana/dashboard.json`
   - Click "Load"
   - Select "Prometheus" as the data source
   - Click "Import"

6. **View the dashboard** and take your screenshot!

## Detailed Steps

### Step 1: Verify Services are Running

Check that all services are up:
```bash
docker compose ps
```

You should see:
- ✅ zookeeper (healthy)
- ✅ kafka (healthy)
- ✅ mlflow (healthy)
- ✅ api (healthy)
- ✅ prometheus (running)
- ✅ grafana (running)

### Step 2: Generate Traffic

To see metrics in the dashboard, you need to generate some requests. You have several options:

**Option A: Run the load test** (recommended for demo):
```bash
python tests/load_test.py
```

**Option B: Make manual requests:**
```bash
# Make a few requests
for i in {1..20}; do
  curl -X POST http://localhost:8000/predict \
    -H "Content-Type: application/json" \
    -d '{"rows": [{"ret_mean": 0.001, "ret_std": 0.01, "n": 100}]}'
  sleep 0.5
done
```

**Option C: Continuous traffic (for longer demo):**
```bash
# Run load test in a loop
while true; do
  python tests/load_test.py
  sleep 30
done
```

### Step 3: Access Grafana

1. Open your browser and go to: **http://localhost:3000**

2. Login:
   - Username: `admin`
   - Password: `admin`

3. You'll be prompted to change the password - you can click "Skip" for now.

### Step 4: Import Dashboard

**Method 1: Upload JSON File**
1. Click on the **"+" icon** in the left sidebar
2. Select **"Import dashboard"**
3. Click **"Upload JSON file"**
4. Navigate to `grafana/dashboard.json` in your project
5. Click **"Load"**
6. Select **"Prometheus"** as the data source (should be pre-selected)
7. Click **"Import"**

**Method 2: Copy/Paste JSON**
1. Click on the **"+" icon** → **"Import dashboard"**
2. Copy the contents of `grafana/dashboard.json`
3. Paste into the "Import via panel json" text area
4. Click **"Load"**
5. Select **"Prometheus"** as the data source
6. Click **"Import"**

### Step 5: View Dashboard

Once imported, you should see:
- **Request Rate** graph
- **Error Rate** graph
- **P50, P95, P99 Latency** graphs
- **Error Rate by Status Code**
- **Request Status Distribution** pie chart
- **Model Version Info**
- **Data Freshness**
- **SLO Compliance** indicator

### Step 6: Take Screenshot

1. Adjust the time range if needed (top right corner)
2. Make sure you have recent data (run load test if needed)
3. Take a screenshot of the dashboard
4. Save it as `grafana_dashboard_screenshot.png` in the project root

## Verifying Prometheus is Scraping

Before viewing Grafana, verify that Prometheus is collecting metrics:

1. **Check Prometheus UI:**
   - Go to: http://localhost:9090
   - Click "Status" → "Targets"
   - Verify `ml-prediction-api` shows as "UP"

2. **Query metrics in Prometheus:**
   - Go to: http://localhost:9090/graph
   - Try query: `predict_req_tot`
   - You should see the metric if the API has received requests

## Troubleshooting

### No metrics showing in Grafana

1. **Check Prometheus is scraping:**
   ```bash
   # Check Prometheus targets
   curl http://localhost:9090/api/v1/targets
   ```

2. **Check API metrics endpoint:**
   ```bash
   curl http://localhost:8000/metrics
   ```
   You should see Prometheus-format metrics.

3. **Generate more traffic:**
   ```bash
   python tests/load_test.py
   ```

4. **Check Grafana data source:**
   - Go to Configuration → Data Sources
   - Verify "Prometheus" is configured and shows "Data source is working"

### Dashboard not loading

1. **Verify JSON is valid:**
   ```bash
   python -m json.tool grafana/dashboard.json > /dev/null
   ```

2. **Try importing again** with a different method

3. **Check Grafana logs:**
   ```bash
   docker logs grafana
   ```

### Prometheus can't reach API

1. **Verify API is running:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Check network connectivity:**
   ```bash
   docker exec prometheus wget -O- http://api:8000/metrics
   ```

3. **Verify Prometheus config:**
   ```bash
   cat docker/prometheus.yml
   ```

## Quick Reference

- **Grafana URL:** http://localhost:3000
- **Prometheus URL:** http://localhost:9090
- **API Metrics:** http://localhost:8000/metrics
- **Dashboard JSON:** `grafana/dashboard.json`
- **Prometheus Config:** `docker/prometheus.yml`

## Tips for Screenshots

1. **Generate enough traffic** - Run load test for at least 30 seconds before screenshot
2. **Set appropriate time range** - Use "Last 5 minutes" or "Last 15 minutes"
3. **Wait for graphs to populate** - Let Grafana refresh a few times (auto-refresh every 10s)
4. **Show key metrics** - Ensure P95 latency, error rate, and request rate are visible
5. **Include SLO indicator** - The SLO compliance panel should be visible

## Next Steps

After taking the screenshot:
1. Save it as `grafana_dashboard_screenshot.png` in project root
2. Add it to your repository
3. Reference it in your documentation

