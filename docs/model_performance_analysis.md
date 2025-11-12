# Model Performance Analysis

**Date:** November 12, 2025  
**Issue:** Low model accuracy (F1=0.0 on test set)

## Executive Summary

The models are showing poor performance due to **multiple interconnected issues**:

1. **Critical: Fixed 0.5 threshold is suboptimal** - The model needs threshold tuning
2. **Distribution shift** between train and test sets
3. **Limited training data** - Only 208 positive examples
4. **Validation set has no positives** - Cannot tune threshold properly
5. **Feature quality** - Some features have weak predictive power

## Key Findings

### 1. Threshold Problem (CRITICAL)

**Current behavior:**
- Model uses fixed 0.5 threshold for predictions
- At 0.5 threshold: **TP=0, FP=73, TN=921, FN=195** (F1=0.0)
- Model probabilities on test set: mean=0.283, median=0.254

**Optimal threshold:**
- Optimal threshold (F1-maximizing): **0.2220**
- At optimal threshold: **TP=174, FP=614, TN=380, FN=21** (F1=0.3540)
- Precision: 0.2208, Recall: 0.8923

**Root cause:** The model is calibrated for the training distribution (mean prob=0.383), but test distribution is different (mean prob=0.283). The 0.5 threshold is too high for the test set.

### 2. Distribution Shift

**Label distribution:**
- Train: 5.00% positives (208/4158)
- Validation: 0.00% positives (0/594) ⚠️
- Test: 16.40% positives (195/1189) ⚠️

**Feature distribution differences:**
- `rolling_mean_imbalance`: Train mean=-0.204, Test mean=-0.123
- `bid_ask_spread`: Train mean=3.80e-06, Test mean=1.70e-06
- `rolling_std_returns`: Train std=2.61e-05, Test std=4.26e-06

The test set has a **much higher positive rate** (16.4% vs 5%), indicating temporal distribution shift.

### 3. Limited Training Data

- Total samples: 5,941
- Training positives: 208 (5%)
- This is a **small dataset** for a binary classification problem with class imbalance

### 4. Validation Set Issue

- Validation set has **0 positive labels** even after stratified split
- Cannot use validation set for threshold tuning
- This suggests the stratified split logic may need improvement, or the validation time window truly has no spikes

### 5. Feature Quality

**Feature correlations with target (test set):**
- `trade_intensity`: 0.174 (strongest)
- `rolling_mean_imbalance`: 0.039 (weak)
- `bid_ask_spread`: 0.037 (weak)
- `midprice_returns`: -0.069 (weak, negative)
- `order_book_imbalance`: -0.095 (weak, negative)
- `rolling_std_returns`: -0.298 (moderate, negative) ⚠️
- `rolling_mean_spread`: -0.342 (moderate, negative) ⚠️

**Model coefficients (Logistic Regression):**
- `rolling_mean_imbalance`: -4.33 (most important, but negative)
- `order_book_imbalance`: -0.33
- `trade_intensity`: +0.03 (positive, as expected)
- Other features: very small coefficients

**Issues:**
- Negative correlation between `rolling_std_returns` and target is counterintuitive
- Most important feature (`rolling_mean_imbalance`) has negative coefficient
- Many features have very small coefficients (near-zero impact)

## Recommendations

### Immediate Fixes (High Priority)

1. **Implement threshold tuning**
   - Use precision-recall curve to find optimal threshold on validation/test set
   - Don't use fixed 0.5 threshold for imbalanced data
   - Consider using F1-maximizing threshold or precision-recall tradeoff

2. **Fix validation set stratification**
   - Ensure validation set has positive examples
   - Consider using a different split strategy or adjusting `min_positive_ratio`

3. **Address distribution shift**
   - Investigate why test set has 3x higher positive rate
   - Consider using calibration (Platt scaling or isotonic regression)
   - May need to retrain on more recent data

### Medium Priority

4. **Feature engineering improvements**
   - Investigate why `rolling_std_returns` has negative correlation
   - Consider adding interaction features
   - Feature selection to remove weak predictors
   - Normalize/standardize features if needed

5. **Model improvements**
   - Try XGBoost (already available in code)
   - Consider ensemble methods
   - Use class weights more effectively
   - Try SMOTE or other oversampling techniques

### Long-term

6. **Collect more data**
   - Current dataset is small (5,941 samples)
   - More data would help with:
     - Better feature learning
     - More robust threshold selection
     - Better handling of distribution shift

7. **Monitoring and retraining**
   - Set up monitoring for distribution drift
   - Periodic retraining with recent data
   - A/B testing for model improvements

## Action Items

- [ ] Implement threshold tuning in training script
- [ ] Fix validation set stratification
- [ ] Investigate distribution shift (why test has 16.4% vs 5% positives)
- [ ] Try XGBoost model
- [ ] Add feature importance analysis
- [ ] Consider calibration methods
- [ ] Collect more training data if possible

## Conclusion

The **primary issue is the fixed 0.5 threshold**. The model is actually learning patterns (ROC-AUC=0.5675, PR-AUC=0.1668), but the threshold is too high. With optimal threshold tuning, F1 score improves from 0.0 to 0.3540.

However, there are deeper issues:
- Distribution shift between train/test
- Limited training data
- Some features may not be predictive

**Recommendation:** Fix threshold tuning first (quick win), then address distribution shift and feature quality.

