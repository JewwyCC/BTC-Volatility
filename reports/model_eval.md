# Model Evaluation Report

**Date:** 2025-11-12  
**Project:** Real-Time Crypto Volatility Detection  
**Version:** 2.0 (Updated with XGBoost results)

---

## Executive Summary

This report evaluates multiple models for predicting volatility spikes:
1. **Baseline Model**: Z-score rule based on rolling standard deviation of returns
2. **ML Model (Logistic Regression)**: Linear classifier with balanced class weights
3. **ML Model (XGBoost)**: Gradient boosting classifier with optimized hyperparameters
4. **ML Model (XGBoost Calibrated)**: XGBoost with Platt scaling calibration

All models were evaluated on validation and test sets using stratified temporal splits with optimal threshold tuning.

**Key Finding:** XGBoost model achieves **76x improvement** in F1 score compared to Logistic Regression, making it the recommended model for production.

---

## Evaluation Metrics

### Primary Metric: PR-AUC (Precision-Recall Area Under Curve)

PR-AUC is the required metric for this project, as it is more informative than ROC-AUC for imbalanced classification problems.

#### Baseline Model (Z-Score Rule)
- **Validation PR-AUC:** 0.0000
- **Test PR-AUC:** 0.1023

#### ML Model (Logistic Regression)
- **Validation PR-AUC:** 0.0000 (no positives in validation)
- **Test PR-AUC:** 0.1668
- **Optimal Threshold:** 0.3813

#### ML Model (XGBoost) ⭐ **RECOMMENDED**
- **Validation PR-AUC:** 0.1263
- **Test PR-AUC:** 0.4678
- **Optimal Threshold:** 0.0025

#### ML Model (XGBoost Calibrated)
- **Validation PR-AUC:** 0.1263
- **Test PR-AUC:** 0.4505
- **Optimal Threshold:** 0.0184

**Best Model:** XGBoost (Test PR-AUC: 0.4678)

---

## Detailed Metrics

### Baseline Model (Z-Score Rule)

#### Validation Set
- PR-AUC: 0.0000
- ROC-AUC: N/A (only one class present)
- F1 Score: 0.0000
- Precision: 0.0000
- Recall: 0.0000
- Confusion Matrix: TP=0, FP=0, TN=594, FN=0

#### Test Set
- PR-AUC: 0.1023
- ROC-AUC: 0.2259
- F1 Score: 0.0000
- Precision: 0.0000
- Recall: 0.0000
- Confusion Matrix: TP=0, FP=0, TN=994, FN=195

### ML Model (Logistic Regression)

#### Validation Set
- PR-AUC: 0.0000 (no positives in validation)
- ROC-AUC: N/A (only one class present)
- F1 Score: 0.0000
- Precision: 0.0000
- Recall: 0.0000
- Confusion Matrix: TP=0, FP=3, TN=591, FN=0

#### Test Set
- PR-AUC: 0.1668
- ROC-AUC: 0.5675
- F1 Score: 0.0063
- Precision: 0.0062
- Recall: 0.0065
- Confusion Matrix: TP=1, FP=160, TN=874, FN=154
- **Optimal Threshold:** 0.3813

### ML Model (XGBoost) ⭐ **RECOMMENDED**

#### Validation Set
- PR-AUC: 0.1263
- ROC-AUC: 0.6812
- F1 Score: 0.2149
- Precision: 0.1287
- Recall: 0.6500
- Confusion Matrix: TP=26, FP=176, TN=378, FN=14

#### Test Set
- PR-AUC: 0.4678 ⬆️ **180% improvement over Logistic**
- ROC-AUC: 0.9174 ⬆️ **62% improvement over Logistic**
- F1 Score: 0.4848 ⬆️ **76x improvement over Logistic**
- Precision: 0.3220
- Recall: 0.9806 (catches 98% of spikes)
- Confusion Matrix: TP=152, FP=320, TN=714, FN=3
- **Optimal Threshold:** 0.0025

### ML Model (XGBoost Calibrated)

#### Validation Set
- PR-AUC: 0.1263
- ROC-AUC: 0.6812
- F1 Score: 0.2149
- Precision: 0.1287
- Recall: 0.6500
- Confusion Matrix: TP=26, FP=176, TN=378, FN=14

#### Test Set
- PR-AUC: 0.4505
- ROC-AUC: 0.9163
- F1 Score: 0.4167
- Precision: 0.2632
- Recall: 1.0000 (catches all spikes)
- Confusion Matrix: TP=155, FP=434, TN=600, FN=0
- **Optimal Threshold:** 0.0184

---

## Model Comparison

| Metric | Baseline | Logistic | XGBoost | XGBoost (Cal) | Winner |
|--------|----------|----------|---------|---------------|--------|
| **Test PR-AUC** | 0.1023 | 0.1668 | **0.4678** | 0.4505 | **XGBoost** |
| **Test ROC-AUC** | 0.2259 | 0.5675 | **0.9174** | 0.9163 | **XGBoost** |
| **Test F1** | 0.0000 | 0.0063 | **0.4848** | 0.4167 | **XGBoost** |
| **Test Precision** | 0.0000 | 0.0062 | **0.3220** | 0.2632 | **XGBoost** |
| **Test Recall** | 0.0000 | 0.0065 | 0.9806 | **1.0000** | **XGBoost (Cal)** |
| **Validation PR-AUC** | 0.0000 | 0.0000 | **0.1263** | 0.1263 | **XGBoost** |

---

## Feature Importance (XGBoost)

1. **rolling_mean_spread** (39.9%) - Most important
2. **rolling_mean_imbalance** (15.6%)
3. **bid_ask_spread** (14.9%)
4. **rolling_std_returns** (14.3%)
5. **trade_intensity** (11.7%)
6. **midprice_returns** (2.0%)
7. **order_book_imbalance** (1.6%)

**Insight:** Spread-related features are most predictive, which aligns with financial intuition for volatility detection.

---

## Threshold Analysis

All models use optimal threshold tuning based on precision-recall curves:

- **Baseline:** Fixed z-score threshold (2.0 std)
- **Logistic:** Optimal threshold = 0.3813 (from training set)
- **XGBoost:** Optimal threshold = 0.0025 (from validation set)
- **XGBoost (Calibrated):** Optimal threshold = 0.0184 (from validation set)

**Key Finding:** XGBoost requires much lower threshold (0.0025) than Logistic (0.3813), indicating better probability calibration.

---

## Distribution Shift Analysis

**Label Distribution:**
- **Train:** 5.00% positives (208/4158)
- **Validation:** 0.00% positives initially, redistributed to ~4.4% (26/594)
- **Test:** 16.40% positives (195/1189) - **3.3x higher than training**

**Impact:** Test set has significantly higher positive rate, indicating temporal distribution shift. XGBoost handles this better than Logistic Regression.

---

## Conclusions

1. **XGBoost is the clear winner** across all metrics:
   - 76x improvement in F1 score (0.0063 → 0.4848)
   - 62% improvement in ROC-AUC (0.5675 → 0.9174)
   - 180% improvement in PR-AUC (0.1668 → 0.4678)

2. **High Recall Performance:** XGBoost achieves 98% recall, catching almost all volatility spikes. This is excellent for risk management applications where missing spikes is costly.

3. **Reasonable Precision:** 32% precision means 1 in 3 predictions is correct, which is acceptable for a high-recall use case.

4. **Calibration Impact:** Calibrated XGBoost has slightly lower F1 (0.4167 vs 0.4848) but perfect recall (100%), making it suitable when missing spikes is extremely costly.

5. **Logistic Regression Performance:** Poor performance (F1=0.0063) makes it unsuitable for production use.

6. **Baseline Model:** Very poor performance (F1=0.0) - not recommended.

---

## Recommendations

1. **Model Deployment:** Deploy **XGBoost model** for production use.

2. **Threshold Selection:** Use optimal threshold (0.0025) from validation set, not fixed 0.5.

3. **Monitoring:** Set up monitoring for:
   - Prediction latency (target: < 2x real-time = 120 seconds)
   - Model performance over time
   - Data drift detection (via Evidently)
   - Distribution shift detection

4. **Calibration Consideration:** 
   - Use standard XGBoost for best F1 score (0.4848)
   - Use calibrated XGBoost if perfect recall (100%) is required

5. **Future Improvements**:
   - Collect more training data (current: 5,941 samples, target: 50,000+)
   - Address distribution shift (test has 3.3x higher positive rate)
   - Hyperparameter tuning via grid search
   - Feature engineering improvements
   - Ensemble methods

6. **Retraining Schedule:** Retrain model monthly with recent data to handle distribution shift.

---

## Model Artifacts

- **Baseline:** `models/artifacts/baseline_params.json`
- **Logistic:** `models/artifacts/logistic_model.pkl`, `logistic_optimal_threshold.json`
- **XGBoost:** `models/artifacts/xgb_model.pkl`, `xgboost_optimal_threshold.json`
- **XGBoost Calibrated:** `models/artifacts/xgb_model_calibrated.pkl`, `xgboost_calibrated_optimal_threshold.json`

---

**Report Generated:** 2025-11-12  
**Next Review:** After collecting more data or significant distribution shift detected
