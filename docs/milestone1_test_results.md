# Milestone 1 Test Results

**Date:** November 12, 2025  
**Status:** ✅ **PASSED**

## Test Summary

All Milestone 1 components have been successfully tested and verified.

---

## 1. Docker Services ✅

### Kafka
- **Status:** Running and healthy
- **Port:** 9092 (external), 29092 (internal)
- **Health Check:** Passed
- **Logs:** No errors, broker started successfully

### MLflow
- **Status:** Running
- **Port:** 5001 (changed from 5000 due to port conflict)
- **Backend:** SQLite
- **Access:** http://localhost:5001

### Zookeeper
- **Status:** Running
- **Port:** 2181

**Command:**
```bash
docker compose -f docker/compose.yaml ps
```

---

## 2. WebSocket Ingestor ✅

### Test Configuration
- **Trading Pair:** BTC-USD
- **Duration:** 1 minute
- **Result:** Successfully ingested 300+ messages

### Key Observations
- ✅ WebSocket connection established successfully
- ✅ Subscribed to `heartbeats` channel (best practice)
- ✅ Subscribed to `ticker` channel for BTC-USD
- ✅ Messages published to Kafka topic `ticks.raw`
- ✅ Data mirrored to local NDJSON file: `data/raw/ticks_20251112.ndjson`
- ✅ Average rate: ~5 messages/second
- ✅ Graceful shutdown working

### Sample Data Structure
```json
{
  "channel": "ticker",
  "timestamp": "2025-11-12T17:35:01.350982182Z",
  "sequence_num": 1,
  "events": [{
    "type": "snapshot",
    "tickers": [{
      "type": "ticker",
      "product_id": "BTC-USD",
      "price": "101673.99",
      "best_bid": "101673.98",
      "best_ask": "101673.99",
      ...
    }]
  }],
  "ingestion_timestamp": "2025-11-12T17:35:01.344696"
}
```

**Command:**
```bash
python scripts/ws_ingest.py --pair BTC-USD --minutes 1
```

---

## 3. Kafka Consumer Validation ✅

### Test Results
- **Topic:** `ticks.raw`
- **Messages Consumed:** 100 (tested)
- **Total Messages Available:** 300+ (from 1-minute ingestion)
- **Message Structure:** Valid JSON with all expected fields
- **Key Fields Present:**
  - `product_id`: BTC-USD
  - `price`: Current price
  - `best_bid`, `best_ask`: Order book data
  - `volume_24_h`, `high_24_h`, `low_24_h`: 24h statistics
  - `ingestion_timestamp`: Added by ingestor

### Sample Message from Kafka
```
Offset: 4886
Partition: 0
Key: BTC-USD
Value keys: ['type', 'product_id', 'price', 'volume_24_h', 'low_24_h', 
             'high_24_h', 'low_52_w', 'high_52_w', 'price_percent_chg_24_h', 
             'best_bid', 'best_ask', 'best_bid_quantity', 'best_ask_quantity', 
             'ingest_timestamp']
```

**Command:**
```bash
python scripts/kafka_consume_check.py --topic ticks.raw --min 100
```

**Result:** ✅ Stream validation successful!

---

## 4. Data Files ✅

### Raw Data Storage
- **Location:** `data/raw/ticks_20251112.ndjson`
- **Format:** NDJSON (newline-delimited JSON)
- **Size:** ~199 KB (for 1 minute of data)
- **Lines:** 361 messages
- **Content:** Mix of subscription confirmations, ticker snapshots, and ticker updates

### Data Quality
- ✅ All messages are valid JSON
- ✅ Ticker data includes price, bid/ask, volume, and 24h statistics
- ✅ Ingestion timestamps added correctly
- ✅ Product IDs correctly identified

---

## 5. Docker Container Build ✅

### Build Test
- **Image:** `volatility-ingestor`
- **Base:** `python:3.10-slim`
- **Status:** ✅ Build successful
- **Size:** Reasonable (optimized with multi-stage considerations)

**Command:**
```bash
docker build -f docker/Dockerfile.ingestor -t volatility-ingestor .
```

**Result:** ✅ Container builds successfully

---

## Issues Found & Resolved

### 1. Port Conflict (Resolved)
- **Issue:** Port 5000 already in use
- **Solution:** Changed MLflow port to 5001 in `docker/compose.yaml`
- **Status:** ✅ Fixed

### 2. Python 3.13 Compatibility (Resolved)
- **Issue:** Pandas 2.1.4 doesn't compile with Python 3.13
- **Solution:** Updated `requirements.txt` to use `pandas>=2.2.0` (flexible version)
- **Status:** ✅ Fixed (core dependencies installed separately for testing)

### 3. Syntax Error in Reconnection Logic (Resolved)
- **Issue:** `nonlocal` scope error in reconnection function
- **Solution:** Simplified reconnection logic
- **Status:** ✅ Fixed

### 4. Dockerfile CMD (Resolved)
- **Issue:** CMD doesn't accept arguments properly
- **Solution:** Changed to ENTRYPOINT to allow argument passing
- **Status:** ✅ Fixed

---

## Performance Metrics

### Ingestion Rate
- **Messages per minute:** ~300
- **Messages per second:** ~5
- **Data size:** ~199 KB/minute
- **Kafka latency:** < 1 second

### Resource Usage
- **Docker containers:** 3 (Kafka, Zookeeper, MLflow)
- **Memory:** Reasonable (typical Docker Compose setup)
- **CPU:** Low during idle, moderate during ingestion

---

## Milestone 1 Checklist

- [x] Docker Compose setup for Kafka and MLflow
- [x] WebSocket ingestor connects to Coinbase API
- [x] Subscribes to ticker channel correctly
- [x] Implements heartbeats subscription
- [x] Publishes messages to Kafka topic `ticks.raw`
- [x] Mirrors data to local NDJSON files
- [x] Kafka consumer validation script works
- [x] Reconnection logic implemented
- [x] Graceful shutdown handling
- [x] Dockerfile builds successfully
- [x] Configuration files in place
- [x] Documentation created

---

## Next Steps (Milestone 2)

1. Build feature engineering pipeline (`features/featurizer.py`)
2. Create replay script (`scripts/replay.py`)
3. Conduct EDA in Jupyter notebook
4. Generate Evidently report for data quality and drift
5. Define volatility threshold (τ) based on EDA

---

## Test Commands Reference

```bash
# Start services
docker compose -f docker/compose.yaml up -d

# Check services
docker compose -f docker/compose.yaml ps

# Ingest data (1 minute)
python scripts/ws_ingest.py --pair BTC-USD --minutes 1

# Validate Kafka stream
python scripts/kafka_consume_check.py --topic ticks.raw --min 100

# Build container
docker build -f docker/Dockerfile.ingestor -t volatility-ingestor .

# Check data files
ls -lh data/raw/
head -1 data/raw/ticks_*.ndjson | python3 -m json.tool
```

---

**Test Status:** ✅ **ALL TESTS PASSED**

Milestone 1 is complete and ready for submission.

