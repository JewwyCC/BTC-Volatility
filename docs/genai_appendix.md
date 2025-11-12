# Generative AI Usage Appendix

This document tracks the use of generative AI tools (e.g., ChatGPT, GitHub Copilot) in this project.

## Format

For each use, document:
- **Prompt (summary)**: Brief description of what was requested
- **Used in**: File(s) where the AI-generated content was used
- **Verification**: How the output was reviewed and modified

---

## AI Usage Log

### Entry 1
**Prompt (summary)**: "Generate project structure and Docker Compose setup for Kafka and MLflow"

**Used in**: 
- `docker/compose.yaml`
- Project directory structure
- `README.md`

**Verification**: 
- Reviewed Docker Compose configuration for correct service definitions
- Verified Kafka and MLflow ports and networking
- Tested directory structure matches assignment requirements

---

### Entry 2
**Prompt (summary)**: "Create WebSocket ingestor for Coinbase Advanced Trade API with Kafka producer"

**Used in**: 
- `scripts/ws_ingest.py`

**Verification**: 
- Reviewed WebSocket connection logic against Coinbase API documentation
- Verified subscription message format matches API requirements
- Added heartbeat channel subscription per best practices
- Implemented reconnection logic and error handling
- Tested message parsing and Kafka publishing logic

---

### Entry 3
**Prompt (summary)**: "Create Kafka consumer validation script"

**Used in**: 
- `scripts/kafka_consume_check.py`

**Verification**: 
- Reviewed consumer configuration and message deserialization
- Verified argument parsing and error handling
- Tested message counting and sample display logic

---

### Entry 4
**Prompt (summary)**: "Generate scoping brief template for volatility detection project"

**Used in**: 
- `docs/scoping_brief.md`

**Verification**: 
- Reviewed content for completeness and alignment with assignment requirements
- Ensured all required sections are present (use case, prediction goal, success metric, risk assumptions)
- Content needs to be filled in with project-specific details

---

### Entry 5
**Prompt (summary)**: "Create feature engineering pipeline with Kafka consumer, compute windowed features, and generate Evidently reports"

**Used in**: 
- `features/featurizer.py`
- `scripts/replay.py`
- `scripts/generate_evidently_report.py`
- `notebooks/eda.ipynb`

**Verification**: 
- Reviewed feature computation logic for correctness
- Verified rolling window calculations match specification
- Tested replay script produces identical features
- Validated Evidently report generation with correct API usage

---

### Entry 6
**Prompt (summary)**: "Create model training script with baseline and ML models, time-based splits, and MLflow logging"

**Used in**: 
- `models/train.py`
- `models/infer.py`
- `scripts/generate_eval_report.py`

**Verification**: 
- Reviewed time-based split logic to prevent data leakage
- Verified MLflow logging includes all required metrics (PR-AUC, F1, etc.)
- Tested baseline (z-score) and ML (Logistic Regression) model implementations
- Validated inference latency meets < 2x real-time requirement
- Confirmed model artifacts are saved correctly

---

### Entry 7
**Prompt (summary)**: "Generate Model Card v1 and evaluation report with PR-AUC metrics"

**Used in**: 
- `docs/model_card_v1.md`
- `scripts/generate_eval_report.py`
- `reports/model_eval.md`

**Verification**: 
- Reviewed Model Card structure and completeness
- Verified evaluation report includes PR-AUC (required metric)
- Ensured all sections align with assignment requirements
- Confirmed metrics are extracted correctly from MLflow

---

**Note**: This log documents GenAI usage across all three milestones.

