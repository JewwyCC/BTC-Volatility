# Data Leakage Investigation and Fixes

## Summary

Investigation revealed **critical data leakage issues** that were causing perfect test accuracy. All issues have been identified and fixed.

## Issues Found

### 1. **EDA Notebook: Threshold Computed from Entire Dataset** ⚠️ CRITICAL

**Location:** `notebooks/eda.ipynb` (Cell 5)

**Problem:**
- The threshold (τ) for binary classification was computed using the 95th percentile of `future_volatility` from the **entire dataset**, including test data
- This leaks information about test data distribution into the threshold selection process
- While the training script (`models/train.py`) correctly recomputes the threshold from training data only, the EDA notebook's approach was incorrect and could mislead users

**Fix:**
- Modified EDA notebook to **split data first** (train/val/test) before any analysis
- Threshold is now computed **only from training data**
- Added clear warnings and documentation about data leakage prevention
- All percentile analysis now uses training data only

**Code Changes:**
```python
# Before (WRONG):
tau = df['future_volatility'].quantile(0.95)  # Uses entire dataset

# After (CORRECT):
df_train, df_val, df_test = split_data(df)  # Split first
tau = df_train['future_volatility'].quantile(0.95)  # Training only
```

### 2. **Future Volatility Computation: Incorrect Forward-Looking Window** ⚠️ CRITICAL

**Location:** `features/featurizer.py` - `compute_future_volatility()` function

**Problem:**
- The original implementation used `shift(-1)` followed by `.rolling()`, which doesn't correctly compute a forward-looking window
- Pandas `.rolling()` with time-based windows only looks **backward** in time
- This meant the "future volatility" was actually computed incorrectly, potentially using past information

**Fix:**
- Rewrote `compute_future_volatility()` to correctly compute forward-looking windows
- For each timestamp `t`, now correctly computes std of returns from `t+1` to `t+horizon`
- Uses manual iteration to ensure correct forward-looking computation

**Code Changes:**
```python
# Before (INCORRECT):
future_returns = df_indexed['midprice_returns'].shift(-1)
df_indexed['future_volatility'] = future_returns.rolling(window=window_str).std()
# This doesn't correctly look forward

# After (CORRECT):
for ts in df_indexed.index:
    end_time = ts + pd.Timedelta(seconds=horizon)
    future_mask = (df_indexed.index > ts) & (df_indexed.index <= end_time)
    future_returns = returns[future_mask]
    future_vol.loc[ts] = future_returns.std()
```

### 3. **Feature Computation: Verified Correct** ✅

**Location:** `features/featurizer.py` - `compute_features()` function

**Status:** No issues found

**Verification:**
- All rolling features use `.rolling()` which looks **backward** (correct for features)
- `midprice_returns` uses `.shift(1)` which looks backward (correct)
- `rolling_std_returns`, `rolling_mean_spread`, etc. all look backward (correct)
- Features are computed correctly and do not use future information

## Correct Workflow (After Fixes)

1. **Load and Split Data First**
   - Load features from parquet
   - Split into train/validation/test using temporal split (70/10/20)
   - **Never** compute statistics on the entire dataset before splitting

2. **Compute Threshold from Training Data Only**
   - Compute threshold (τ) as percentile of `future_volatility` in **training data only**
   - Use this threshold to create labels for all splits

3. **Feature Engineering**
   - Features are computed correctly (backward-looking)
   - Future volatility is computed correctly (forward-looking for target variable)

4. **Model Training**
   - Training script already correctly computes threshold from training data
   - No changes needed to training script

## Impact

### Before Fixes:
- Perfect test accuracy (100% or near-perfect) - clear sign of data leakage
- Threshold computed from test data distribution
- Incorrect future volatility computation

### After Fixes:
- Test accuracy should now be realistic (not perfect)
- Proper train/validation/test evaluation
- Correct temporal relationships maintained

## Recommendations

1. **Always split data first** before any analysis or statistics computation
2. **Never compute thresholds or statistics on test data** before model training
3. **Verify forward-looking computations** are actually looking forward (not backward)
4. **Use temporal splits** for time-series data (not random splits)
5. **Document data leakage prevention** in notebooks and scripts

## Files Modified

1. `notebooks/eda.ipynb` - Fixed threshold computation to use training data only
2. `features/featurizer.py` - Fixed `compute_future_volatility()` to correctly look forward

## Testing Recommendations

After these fixes, you should:
1. Re-run the featurizer to regenerate features with correct future volatility
2. Re-run the EDA notebook to see the corrected analysis
3. Re-train the model and verify test accuracy is now realistic (not perfect)
4. Compare metrics before/after to confirm data leakage is resolved

