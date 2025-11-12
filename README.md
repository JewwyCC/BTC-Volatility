# Real-Time Crypto Volatility Detection Pipeline

A real-time data pipeline that connects to Coinbase's Advanced Trade WebSocket API, collects live market data, streams it to Kafka, processes features, and trains models to detect short-term volatility spikes.

## Project Structure

```
.
├── data/
│   ├── raw/              # Captured raw WebSocket data (NDJSON)
│   └── processed/        # Processed features (Parquet)
├── features/             # Feature engineering pipeline
├── models/               # Model training and inference
│   └── artifacts/        # Saved model artifacts
├── notebooks/            # EDA and analysis notebooks
├── reports/              # Evaluation and drift reports
│   └── evidently/        # Evidently HTML/JSON reports
├── scripts/              # Utility scripts
│   ├── ws_ingest.py      # WebSocket ingestor
│   ├── kafka_consume_check.py  # Kafka validation
│   └── replay.py         # Feature replay script
├── docker/               # Docker configuration
│   ├── compose.yaml      # Kafka + MLflow services
│   └── Dockerfile.ingestor  # Ingestor container
├── docs/                 # Documentation
│   ├── scoping_brief.md  # Project scoping document
│   ├── feature_spec.md   # Feature specifications
│   └── model_card_v1.md  # Model documentation
├── handoff/              # Team handoff materials
├── config.yaml           # Configuration file
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

## Quick Start

### 1. Prerequisites

- Docker and Docker Compose
- Python 3.10+
- Git

### 2. Setup

```bash
# Clone the repository (if applicable)
# cd FOAI_Proj1

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file template
cp .env.example .env
# Edit .env if needed (not required for public data)
```

### 3. Start Services

```bash
# Start Kafka and MLflow
docker compose -f docker/compose.yaml up -d

# Verify services are running
docker compose -f docker/compose.yaml ps

# Check Kafka is ready (wait ~30 seconds)
docker compose -f docker/compose.yaml logs kafka | grep "started"
```

### 4. Ingest Data

```bash
# Ingest 15 minutes of ticker data for BTC-USD
python scripts/ws_ingest.py --pair BTC-USD --minutes 15

# Or run indefinitely (Ctrl+C to stop)
python scripts/ws_ingest.py --pair BTC-USD
```

### 5. Validate Stream

```bash
# Check that messages are in Kafka
python scripts/kafka_consume_check.py --topic ticks.raw --min 100
```

### 6. Build Features (Milestone 2)

```bash
# Build features from Kafka stream
python features/featurizer.py --topic_in ticks.raw --topic_out ticks.features

# Replay from saved raw data
python scripts/replay.py --raw data/raw/*.ndjson --out data/processed/features.parquet
```

### 7. Train Models (Milestone 3)

```bash
# Train models and log to MLflow
python models/train.py --features data/processed/features.parquet

# Run inference
python models/infer.py --features data/processed/features_test.parquet
```

## Configuration

Edit `config.yaml` to customize:
- Kafka broker settings
- Coinbase WebSocket configuration
- Feature engineering parameters
- Model training settings

## Accessing Services

- **MLflow UI**: http://localhost:5000
- **Kafka**: localhost:9092

## Milestones

### Milestone 1: Streaming Setup & Scoping ✓
- [x] Docker Compose for Kafka and MLflow
- [x] WebSocket ingestor
- [x] Kafka consumer validation
- [x] Scoping brief

### Milestone 2: Feature Engineering, EDA & Evidently
- [ ] Feature computation pipeline
- [ ] Replay script
- [ ] EDA notebook
- [ ] Evidently reports

### Milestone 3: Modeling, Tracking, Evaluation
- [ ] Model training (baseline + ML)
- [ ] MLflow logging
- [ ] Model evaluation
- [ ] Model card

## Testing

```bash
# Test Docker services
docker compose -f docker/compose.yaml ps

# Test ingestor (15 minutes)
python scripts/ws_ingest.py --pair BTC-USD --minutes 15

# Test Kafka consumer
python scripts/kafka_consume_check.py --topic ticks.raw --min 100

# Test container build
docker build -f docker/Dockerfile.ingestor -t volatility-ingestor .
docker run --rm volatility-ingestor --pair BTC-USD --minutes 1
```

## Troubleshooting

**Kafka not starting:**
- Check Docker logs: `docker compose -f docker/compose.yaml logs kafka`
- Ensure ports 9092 and 9093 are not in use
- Wait 30-60 seconds for Kafka to fully initialize

**WebSocket connection issues:**
- Verify internet connection
- Check Coinbase API status
- Review WebSocket logs in ingestor output

**No messages in Kafka:**
- Verify ingestor is running and connected
- Check Kafka topic exists: `docker exec kafka kafka-topics --list --bootstrap-server localhost:9092`
- Check consumer group: `docker exec kafka kafka-consumer-groups --bootstrap-server localhost:9092 --list`

## Development

```bash
# Format code (if using black)
black scripts/ features/ models/

# Type checking (if using mypy)
mypy scripts/ features/ models/

# Run tests (if available)
pytest tests/
```

## License

This project is for educational purposes only.

## Notes

- This assignment uses **public market data only**. Do not place trades.
- All secrets should be in `.env` (never committed).
- See `docs/genai_appendix.md` for GenAI usage documentation.

