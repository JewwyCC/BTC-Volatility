# Scoping Brief: Real-Time Crypto Volatility Detection

**Date:** [Fill in date]  
**Author:** [Your name]  
**Project:** Individual Programming Assignment - Milestone 1

---

## 1. Use Case

**Problem Statement:**
Cryptocurrency markets exhibit high volatility, with rapid price movements that can occur within seconds. Traders, risk managers, and automated systems need early warning signals to detect when volatility is about to spike, enabling them to adjust positions, manage risk, or trigger automated responses.

**Target Users:**
- Algorithmic traders seeking volatility-based trading signals
- Risk management systems requiring real-time volatility alerts
- Market makers needing to adjust spreads based on volatility expectations

**Value Proposition:**
By predicting short-term volatility spikes 60 seconds in advance, users can:
- Reduce exposure during high-volatility periods
- Optimize position sizing and risk limits
- Improve execution timing for large orders
- Enhance automated trading strategies

---

## 2. 60-Second Prediction Goal

**Objective:**
Predict whether the rolling standard deviation of midprice returns over the next 60 seconds will exceed a predefined threshold (τ), indicating a volatility spike.

**Prediction Horizon:** 60 seconds  
**Update Frequency:** Real-time (as new ticks arrive, typically every few seconds)

**Output:**
- Binary classification: `1` if volatility spike is predicted, `0` otherwise
- Optional: Probability score for the prediction

---

## 3. Success Metric

**Primary Metric:**
- **PR-AUC (Precision-Recall Area Under Curve)**: Required metric for evaluation
  - Target: PR-AUC > 0.65 (baseline expectation)
  - Rationale: In imbalanced classification problems (volatility spikes are rare), PR-AUC is more informative than ROC-AUC

**Secondary Metrics:**
- **F1 Score @ optimal threshold**: Balance between precision and recall
- **Latency**: Inference time < 2x real-time (i.e., if window is 60s, inference should complete in < 120s)
- **False Positive Rate**: Keep low to avoid unnecessary alerts

**Baseline Comparison:**
- Compare against a simple rule-based baseline (e.g., z-score threshold on recent volatility)
- ML model should outperform baseline by at least 10% in PR-AUC

---

## 4. Risk Assumptions

**Data Quality Risks:**
- **WebSocket disconnections**: Coinbase API may disconnect; mitigated by auto-reconnect logic
- **Missing ticks**: Network issues may cause gaps; handled by interpolation or forward-fill
- **Data drift**: Market microstructure changes over time; monitored via Evidently reports

**Model Risks:**
- **Concept drift**: Volatility patterns may change (e.g., during market regime shifts)
- **Overfitting**: Limited training data may lead to poor generalization
- **Latency**: Feature computation must be fast enough for real-time use

**Operational Risks:**
- **Kafka failures**: Single-node setup has no redundancy; mitigated by local file mirroring
- **Resource constraints**: High message rates may overwhelm system; monitor and throttle if needed

**Assumptions:**
1. Coinbase WebSocket API remains stable and accessible
2. Market data is sufficiently representative for training
3. 60-second prediction horizon is appropriate for the use case
4. Historical patterns are somewhat predictive of future volatility

---

## 5. Technical Constraints

- **Real-time processing**: Must process ticks as they arrive (no batch delays)
- **Resource limits**: Running on local machine with Docker Compose
- **Data privacy**: Using public market data only (no authentication required)
- **Reproducibility**: All features must be replayable from raw data

---

## 6. Next Steps (Milestone 2)

1. Build feature engineering pipeline
2. Conduct exploratory data analysis to set volatility threshold (τ)
3. Generate first Evidently report for data quality and drift
4. Validate feature replay consistency

---

**Status:** ✓ Complete for Milestone 1

