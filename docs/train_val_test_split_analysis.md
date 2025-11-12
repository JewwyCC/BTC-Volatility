# Train/Validation/Test Split Analysis

**Date:** November 12, 2025  
**Project:** Real-Time Crypto Volatility Detection

---

## Executive Summary

This document explains in detail how the train/validation/test data is being split and why the validation set (and sometimes test set) may have no volatility spikes (positive labels).

---

## 1. Data Split Strategy

### 1.1 Temporal Split (Chronological)

The data is split **temporally** (chronologically), not randomly. This is critical for time series data to avoid data leakage.

**Split Configuration:**
- **Train:** 70% (first 70% of data by timestamp)
- **Validation:** 10% (next 10% of data by timestamp)
- **Test:** 20% (last 20% of data by timestamp)

**Implementation:**
```python
def time_based_split(df: pd.DataFrame, train_pct: float = 0.7, 
                     val_pct: float = 0.1, test_pct: float = 0.2):
    # Ensure data is sorted by timestamp
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    n = len(df)
    n_train = int(n * train_pct)
    n_val = int(n * val_pct)
    
    df_train = df.iloc[:n_train].copy()
    df_val = df.iloc[n_train:n_train + n_val].copy()
    df_test = df.iloc[n_train + n_val:].copy()
    
    return df_train, df_val, df_test
```

**Example (from actual data):**
- Total samples: 5,941
- Time range: 2025-11-12 17:35:01 to 2025-11-12 17:58:09 (23.1 minutes)
- **Train:** 4,158 samples (70.0%) - 17:35:01 to 17:53:01 (18 minutes)
- **Validation:** 594 samples (10.0%) - 17:53:01 to 17:54:47 (1.5 minutes)
- **Test:** 1,189 samples (20.0%) - 17:54:47 to 17:58:09 (3.4 minutes)

---

## 2. Threshold Computation (τ)

### 2.1 How Threshold is Computed

The threshold **τ** is computed from **training data only** (95th percentile of `future_volatility`).

**Implementation:**
```python
def compute_threshold_from_training(df_train: pd.DataFrame, 
                                    percentile: float = 0.95) -> float:
    """Compute threshold (tau) as percentile of future volatility in training data."""
    tau = df_train['future_volatility'].quantile(percentile)
    return tau
```

**Example:**
- Training data 95th percentile: τ = 0.00003460
- This means 5% of training samples have `future_volatility >= 0.00003460`

### 2.2 Label Creation

Labels are created for **all splits** using the **same threshold** (computed from training data):

```python
def create_labels(df: pd.DataFrame, tau: float) -> pd.Series:
    """Create binary labels based on threshold."""
    return (df['future_volatility'] >= tau).astype(int)
```

**Why use training threshold for all splits?**
- In production, we only have training data to compute the threshold
- We want to evaluate on validation/test using the same threshold that would be used in production
- This ensures realistic evaluation

---

## 3. Why Validation/Test May Have No Spikes

### 3.1 The Problem

**Observation:** Validation set has **0 positive labels** (no spikes) even though:
- Training set has 208 positives (5.00%)
- Test set has 195 positives (16.40%)

**Root Cause:** Volatility spikes are **clustered in time**, not uniformly distributed.

### 3.2 Detailed Analysis

**Volatility Statistics by Split:**
- **Train:**
  - Mean: 0.00002795
  - Std: 0.00000429
  - Max: 0.00005743
  - 95th percentile: 0.00003460 (τ)

- **Validation:**
  - Mean: 0.00002425 (lower than train)
  - Std: 0.00000155 (lower than train)
  - Max: 0.00002652 (lower than τ!)
  - 95th percentile: 0.00002614 (lower than τ)

- **Test:**
  - Mean: 0.00002671 (lower than train)
  - Std: 0.00000774 (higher than train)
  - Max: 0.00004237 (higher than τ!)
  - 95th percentile: 0.00003649 (higher than τ)

**Key Insight:**
- Validation's **maximum volatility (0.00002652) is LOWER than the training threshold (0.00003460)**
- Therefore, **NO samples in validation exceed the threshold**
- The validation period happened to be a "calm" period with no high volatility events

### 3.3 Why This Happens

1. **Temporal Clustering:** Volatility spikes are clustered in time (not uniformly distributed)
   - Market volatility tends to occur in bursts
   - Quiet periods can last minutes to hours
   - High volatility periods are often short-lived but intense

2. **Short Data Collection Period:** 
   - Current dataset: 23.1 minutes of data
   - Validation period: 1.5 minutes
   - If volatility spikes are rare (5% of samples), and they're clustered, a short validation period may miss them entirely

3. **Threshold Computed from Training Only:**
   - Training data may have different volatility characteristics than validation/test
   - If training period has high volatility, but validation period is calm, validation will have no spikes

---

## 4. Why Test Has Spikes

**Observation:** Test set has **195 positive labels (16.40%)**, which is **higher than training (5.00%)**.

**Why:**
- Test period contains high volatility events
- Test's maximum volatility (0.00004237) exceeds τ (0.00003460)
- Test's 95th percentile (0.00003649) is higher than τ
- The test period happened to be a "volatile" period with many spikes

**Implication:**
- Test set has **more positive labels than training set**
- This suggests the test period had more volatility than the training period
- The model may not be well-calibrated for the test distribution

---

## 5. Solutions

### 5.1 Stratified Temporal Split (Implemented)

The code includes a `stratified_temporal_split` function that redistributes positive samples across splits while maintaining temporal order.

**How it works:**
1. Do initial temporal split
2. Create labels based on threshold
3. If val/test have no positives, redistribute some from training
4. Maintain approximate temporal order by swapping positives near split boundaries

**Implementation:**
```python
def stratified_temporal_split(df: pd.DataFrame, tau: float, 
                              train_pct: float = 0.7,
                              val_pct: float = 0.1, 
                              test_pct: float = 0.2,
                              min_positive_ratio: float = 0.01) -> tuple:
    # ... redistributes positives to ensure all splits have some
```

**Configuration:**
```yaml
model:
  split_strategy: 'stratified_temporal'  # Use stratified split
  min_positive_ratio: 0.01  # 1% minimum positives in each split
```

### 5.2 Lower Threshold Percentile

Instead of 95th percentile, use 90th percentile to capture more positives:

```yaml
model:
  threshold_percentile: 90  # Instead of 95
```

**Trade-off:**
- More positive labels in all splits
- But threshold may be too low (less meaningful spikes)

### 5.3 Collect More Data

Collect more data over a longer time period to ensure:
- Spikes are distributed across time periods
- Validation/test periods are more representative
- More stable threshold estimation

### 5.4 Use Global Threshold

Compute threshold from **all data** (not just training):

```python
tau = df['future_volatility'].quantile(0.95)  # All data
```

**Trade-off:**
- Not realistic for production (we don't have future data)
- But ensures all splits have positives for evaluation

---

## 6. Code Reference

### 6.1 Split Functions

**Location:** `models/train.py`

- **`time_based_split()`** (lines 203-229): Standard temporal split
- **`stratified_temporal_split()`** (lines 232-371): Stratified temporal split with redistribution

### 6.2 Threshold Computation

**Location:** `models/train.py`

- **`compute_threshold_from_training()`** (lines 56-60): Compute threshold from training data
- **`create_labels()`** (lines 63-65): Create binary labels using threshold

### 6.3 Main Training Logic

**Location:** `models/train.py`

- **`main()`** (lines 374-663): Main training function that:
  1. Loads data
  2. Splits data (temporal or stratified_temporal)
  3. Computes threshold from training data
  4. Creates labels for all splits
  5. Trains and evaluates models

---

## 7. Visualization

A visualization script is available to analyze the temporal distribution:

**Script:** `scripts/visualize_split_distribution.py`

**Output:** `reports/split_distribution_analysis.png`

**Visualization shows:**
1. Temporal distribution of `future_volatility` across splits
2. Histogram of `future_volatility` by split
3. Spike locations over time

**Run:**
```bash
python scripts/visualize_split_distribution.py
```

---

## 8. Recommendations

1. **Use Stratified Temporal Split:**
   - Already implemented in `train.py`
   - Set `split_strategy: 'stratified_temporal'` in `config.yaml`
   - Ensures all splits have positive labels

2. **Monitor Split Distributions:**
   - Run `scripts/visualize_split_distribution.py` regularly
   - Check label distribution in each split
   - Ensure splits are representative

3. **Collect More Data:**
   - Collect data over longer time periods (hours/days)
   - Ensure spikes are distributed across time
   - More stable threshold estimation

4. **Consider Alternative Thresholds:**
   - Experiment with different percentiles (90th, 85th)
   - Use domain knowledge to set threshold
   - Evaluate threshold sensitivity

5. **Evaluate on Multiple Splits:**
   - Use time-based cross-validation
   - Evaluate on multiple validation/test periods
   - Ensure model generalizes across time periods

---

## 9. Summary

**Key Points:**
1. Data is split **temporally** (chronologically) - 70%/10%/20%
2. Threshold **τ** is computed from **training data only** (95th percentile)
3. Labels are created using the **same threshold** for all splits
4. **Validation has no spikes** because:
   - Volatility spikes are clustered in time
   - Validation period is a "calm" period
   - Validation's max volatility < training threshold
5. **Test has spikes** because:
   - Test period contains high volatility events
   - Test's max volatility > training threshold
6. **Solutions:**
   - Use stratified temporal split (already implemented)
   - Lower threshold percentile
   - Collect more data
   - Use global threshold (not recommended for production)

---

## 10. References

- **Code:** `models/train.py`
- **Config:** `config.yaml`
- **Visualization:** `scripts/visualize_split_distribution.py`
- **Analysis:** `scripts/analyze_label_distribution.py`

