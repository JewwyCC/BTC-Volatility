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
│   ├── kafka_predictor.py  # Streaming prediction consumer
│   ├── replay.py         # Feature replay script
│   └── load_test.py      # Load test
├── docker/               # Docker configuration
│   ├── compose.yaml      # Kafka + MLflow services
│   └── Dockerfile.ingestor  # Ingestor container
├── docs/                 # Documentation
│   ├── scoping_brief.md  # Project scoping document
│   ├── feature_spec.md   # Feature specifications
│   ├── model_card_v1.md  # Model documentation
│   ├── end_to_end_validation.md  # Complete pipeline validation guide
│   └── next_steps.md     # Implementation roadmap
├── handoff/              # Team handoff materials
├── config.yaml           # Configuration file
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

## Quick Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
docker compose up -d
python -m uvicorn api_v1:api --reload
```

**Test the system:**
```bash
# Quick test
./scripts/quick_test.sh

# Comprehensive test
python scripts/test_system.py
```

See detailed setup instructions below.

**Model Performance:**
- **XGBoost:** F1=0.4848, ROC-AUC=0.9174, PR-AUC=0.4678 ✅ (Recommended)
- **Logistic Regression:** F1=0.0063, ROC-AUC=0.5675, PR-AUC=0.1668

See `docs/improvements_complete.md` for detailed performance comparison.

## Configuration

Edit `config.yaml` to customize:
- Kafka broker settings
- Coinbase WebSocket configuration
- Feature engineering parameters
- Model training settings
- MLflow tracking URI and model loading preferences

## Accessing Services

- **MLflow UI**: http://localhost:5001
- **Kafka**: localhost:9092
- **API**: http://localhost:8000 (when running `uvicorn api_v1:api`)

## Testing

```bash
# Test Docker services
docker compose -f docker/compose.yaml ps

# Test ingestor (15 minutes)
python scripts/ws_ingest.py --pair BTC-USD --minutes 15

# Test Kafka consumer
python scripts/kafka_consume_check.py --topic ticks.raw --min 100

# Test streaming predictions
python scripts/kafka_predictor.py --topic_in ticks.features --topic_out ticks.predictions

# Test API (loads model from MLflow)
python -m uvicorn api_v1:api --reload

# Test container build
docker build -f docker/Dockerfile.ingestor -t volatility-ingestor .
docker run --rm volatility-ingestor --pair BTC-USD --minutes 1
```

## End-to-End Pipeline

Quick start:
1. Start services: `docker compose -f docker/compose.yaml up -d`
2. Train model: `python models/train.py --model_type xgboost`
3. Ingest data: `python scripts/ws_ingest.py --pair BTC-USD --minutes 15`
4. Process features: `python features/featurizer.py`
5. Make predictions: `python scripts/kafka_predictor.py`

## Model Loading

The API now loads models from MLflow by default (configurable in `config.yaml`):

- **MLflow loading**: Set `mlflow.model_source: "latest"` or `"run_id"`
- **Local fallback**: Set `mlflow.model_source: "local"` or if MLflow is unavailable
- **Version info**: Check `/version` endpoint for model source and MLflow run ID

See `config.yaml` for MLflow configuration options.

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

