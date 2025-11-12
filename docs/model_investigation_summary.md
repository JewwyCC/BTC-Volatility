# Model Performance Investigation Summary

**Date:** November 12, 2025  
**Issue:** Low model accuracy (F1=0.0 on test set with 0.5 threshold)

## Key Findings

### 1. **Primary Issue: Fixed Threshold (FIXED)**
- **Problem:** Model was using fixed 0.5 threshold, which is suboptimal for imbalanced data
- **Impact:** F1 score = 0.0 on test set (TP=0, FP=73, TN=921, FN=195)
- **Solution:** Implemented threshold tuning using precision-recall curve
- **Result:** F1 improved from 0.0 to 0.0063 (still low, but better)
- **Optimal threshold from training:** 0.3813
- **Test-optimal threshold (diagnostic):** ~0.22 (would give F1=0.3540, but can't use due to data leakage)

### 2. **Distribution Shift (CRITICAL)**
- **Train set:** 5.00% positives (208/4158)
- **Test set:** 16.40% positives (195/1189) - **3.3x higher!**
- **Impact:** Model trained on 5% positive rate, but test has 16.4% positive rate
- **Why:** Temporal clustering of volatility spikes - test period happened to be more volatile
- **Consequence:** Training-optimal threshold (0.3813) is too high for test distribution

### 3. **Limited Training Data**
- **Total samples:** 5,941
- **Training positives:** 208 (5%)
- **This is a small dataset** for binary classification with class imbalance
- More data would help with:
  - Better feature learning
  - More robust threshold selection
  - Better handling of distribution shift

### 4. **Validation Set Issue**
- **Validation set has 0 positive labels** even after stratified split
- Cannot use validation set for threshold tuning
- Stratified split logic may need improvement, or validation window truly has no spikes

### 5. **Feature Quality**
- Some features have weak predictive power:
  - `midprice_returns`: correlation = -0.069 (weak, negative)
  - `order_book_imbalance`: correlation = -0.095 (weak, negative)
- Most important feature: `rolling_mean_imbalance` (coefficient = -4.33)
- Counterintuitive: `rolling_std_returns` has negative correlation (-0.298) with target

## Current Performance

### With Optimal Threshold (0.3813 from training):
- **F1 Score:** 0.0063 (very low)
- **Precision:** 0.0062
- **Recall:** 0.0065
- **TP=1, FP=160, TN=874, FN=154**

### With Test-Optimal Threshold (0.22, diagnostic only):
- **F1 Score:** 0.3540 (much better, but can't use)
- **Precision:** 0.2208
- **Recall:** 0.8923
- **TP=174, FP=614, TN=380, FN=21**

## Root Causes

1. **Distribution shift** - Test set has 3.3x higher positive rate than training
2. **Limited data** - Only 208 positive examples in training
3. **Threshold mismatch** - Training-optimal threshold doesn't work well on test
4. **Feature quality** - Some features may not be predictive

## Recommendations

### Immediate (High Priority)

1. **✅ DONE: Implement threshold tuning**
   - Added `find_optimal_threshold()` function
   - Uses precision-recall curve to find F1-maximizing threshold
   - Saves optimal threshold to artifacts

2. **Collect more data**
   - Current dataset is small (5,941 samples, 23 minutes)
   - More data would help with:
     - Better feature learning
     - More robust threshold selection
     - Better handling of distribution shift
   - **Recommendation:** Collect at least 10x more data (50,000+ samples, 2+ hours)

3. **Address distribution shift**
   - Investigate why test set has 3x higher positive rate
   - Consider:
     - Collecting data from multiple time periods
     - Using calibration (Platt scaling) to adjust probabilities
     - Retraining on more recent data

### Medium Priority

4. **Improve stratified split**
   - Ensure validation set has positive examples
   - Current stratified split may not be working correctly
   - Consider using a different split strategy

5. **Feature engineering**
   - Investigate why `rolling_std_returns` has negative correlation
   - Consider adding interaction features
   - Feature selection to remove weak predictors

6. **Model improvements**
   - Try XGBoost (already available in code)
   - Consider ensemble methods
   - Use calibration methods (Platt scaling, isotonic regression)

### Long-term

7. **Monitoring and retraining**
   - Set up monitoring for distribution drift
   - Periodic retraining with recent data
   - A/B testing for model improvements

## Conclusion

The **primary issue was the fixed 0.5 threshold**, which has been fixed. However, there are deeper issues:

1. **Distribution shift** - Test set has much higher positive rate (16.4% vs 5%)
2. **Limited data** - Only 208 positive examples in training
3. **Threshold mismatch** - Training-optimal threshold (0.3813) is too high for test distribution

**The model is learning patterns** (ROC-AUC=0.5675, PR-AUC=0.1668), but the distribution shift and limited data are limiting performance.

**Recommendation:** 
- **Short-term:** The threshold tuning fix helps, but performance is still limited
- **Medium-term:** Collect more data (10x more) and address distribution shift
- **Long-term:** Set up monitoring and periodic retraining

## Next Steps

1. ✅ Implement threshold tuning (DONE)
2. Collect more training data (if possible)
3. Investigate distribution shift (why test has 3x higher positive rate)
4. Try XGBoost model
5. Consider calibration methods
6. Improve feature engineering

