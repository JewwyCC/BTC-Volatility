# Train/Val/Test Split: Detailed Explanation

## How Data is Split

### 1. Temporal Split (Chronological Order)

The data is split **temporally** (chronologically), not randomly:

```203:229:models/train.py
def time_based_split(df: pd.DataFrame, train_pct: float = 0.7, 
                     val_pct: float = 0.1, test_pct: float = 0.2) -> tuple:
    """
    Split data based on time (not random).
    
    Returns: (train, val, test) DataFrames
    """
    # Ensure data is sorted by timestamp
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    n = len(df)
    n_train = int(n * train_pct)
    n_val = int(n * val_pct)
    
    df_train = df.iloc[:n_train].copy()
    df_val = df.iloc[n_train:n_train + n_val].copy()
    df_test = df.iloc[n_train + n_val:].copy()
    
    logger.info(f"\nTime-based split:")
    logger.info(f"  Train: {len(df_train)} samples ({len(df_train)/n*100:.1f}%)")
    logger.info(f"    {df_train['timestamp'].min()} to {df_train['timestamp'].max()}")
    logger.info(f"  Validation: {len(df_val)} samples ({len(df_val)/n*100:.1f}%)")
    logger.info(f"    {df_val['timestamp'].min()} to {df_val['timestamp'].max()}")
    logger.info(f"  Test: {len(df_test)} samples ({len(df_test)/n*100:.1f}%)")
    logger.info(f"    {df_test['timestamp'].min()} to {df_test['timestamp'].max()}")
    
    return df_train, df_val, df_test
```

**Split Proportions:**
- **Train:** 70% (first 70% by timestamp)
- **Validation:** 10% (next 10% by timestamp)
- **Test:** 20% (last 20% by timestamp)

**Example from actual data:**
- Total: 5,941 samples (23.1 minutes of data)
- Train: 4,158 samples (17:35:01 to 17:53:01)
- Validation: 594 samples (17:53:01 to 17:54:47)
- Test: 1,189 samples (17:54:47 to 17:58:09)

---

## 2. Threshold Computation (τ)

### 2.1 How Threshold is Computed

The threshold **τ** is computed from **training data only** (95th percentile):

```56:60:models/train.py
def compute_threshold_from_training(df_train: pd.DataFrame, percentile: float = 0.95) -> float:
    """Compute threshold (tau) as percentile of future volatility in training data."""
    tau = df_train['future_volatility'].quantile(percentile)
    logger.info(f"Computed threshold (τ) from training data: {tau:.8f} ({percentile*100:.0f}th percentile)")
    return tau
```

**Example:**
- Training data 95th percentile: τ = 0.00003460
- This means 5% of training samples have `future_volatility >= 0.00003460`

### 2.2 Label Creation

Labels are created for **all splits** using the **same threshold**:

```63:65:models/train.py
def create_labels(df: pd.DataFrame, tau: float) -> pd.Series:
    """Create binary labels based on threshold."""
    return (df['future_volatility'] >= tau).astype(int)
```

**Why use training threshold for all splits?**
- In production, we only have training data to compute the threshold
- We want to evaluate on validation/test using the same threshold that would be used in production
- This ensures realistic evaluation

---

## 3. Why Validation Has No Spikes

### 3.1 The Problem

**Observation:** Validation set has **0 positive labels** (no spikes) even though:
- Training set has 208 positives (5.00%)
- Test set has 195 positives (16.40%)

### 3.2 Root Cause

**Volatility spikes are CLUSTERED in time**, not uniformly distributed.

**Volatility Statistics:**
- **Train:**
  - Mean: 0.00002795
  - Max: 0.00005743
  - 95th percentile (τ): 0.00003460

- **Validation:**
  - Mean: 0.00002425 (lower than train)
  - Max: 0.00002652 (LOWER than τ!)
  - 95th percentile: 0.00002614 (lower than τ)

- **Test:**
  - Mean: 0.00002671 (lower than train)
  - Max: 0.00004237 (HIGHER than τ!)
  - 95th percentile: 0.00003649 (higher than τ)

**Key Insight:**
- Validation's **maximum volatility (0.00002652) is LOWER than the training threshold (0.00003460)**
- Therefore, **NO samples in validation exceed the threshold**
- The validation period happened to be a "calm" period with no high volatility events

### 3.3 Why This Happens

1. **Temporal Clustering:**
   - Market volatility occurs in bursts
   - Quiet periods can last minutes to hours
   - High volatility periods are short-lived but intense

2. **Short Validation Period:**
   - Validation period: 1.5 minutes (594 samples)
   - If spikes are rare (5% of samples) and clustered, a short validation period may miss them entirely

3. **Threshold from Training Only:**
   - Training period may have different volatility characteristics than validation
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

## 5. Main Training Flow

```410:454:models/train.py
    # Get configuration
    train_pct = 1 - config['model']['validation_split'] - (1 - config['model']['train_test_split'])
    val_pct = config['model']['validation_split']
    test_pct = 1 - config['model']['train_test_split']
    threshold_percentile = config['model'].get('threshold_percentile', 95) / 100.0
    split_strategy = config['model'].get('split_strategy', 'temporal')
    min_positive_ratio = config['model'].get('min_positive_ratio', 0.01)
    
    # Split data based on strategy
    if split_strategy == 'stratified_temporal':
        # For stratified split, we need tau first
        # Compute tau from initial temporal split of training data
        df_temp = df.sort_values('timestamp').reset_index(drop=True)
        n_train_temp = int(len(df_temp) * train_pct)
        df_train_temp = df_temp.iloc[:n_train_temp].copy()
        tau = compute_threshold_from_training(df_train_temp, percentile=threshold_percentile)
        
        # Now do stratified temporal split
        logger.info(f"\nUsing stratified temporal split strategy")
        df_train, df_val, df_test = stratified_temporal_split(
            df, tau, train_pct, val_pct, test_pct, min_positive_ratio
        )
    else:
        # Standard temporal split
        logger.info(f"\nUsing temporal split strategy")
        df_train, df_val, df_test = time_based_split(df, train_pct, val_pct, test_pct)
    
    # Compute threshold from training data (may have been redistributed)
    tau = compute_threshold_from_training(df_train, percentile=threshold_percentile)
    
    # Create labels
    y_train = create_labels(df_train, tau)
    y_val = create_labels(df_val, tau)
    y_test = create_labels(df_test, tau)
    
    logger.info(f"\nLabel distribution:")
    logger.info(f"  Train - Spikes (1): {y_train.sum()} ({y_train.mean()*100:.2f}%), Normal (0): {(1-y_train).sum()} ({(1-y_train.mean())*100:.2f}%)")
    logger.info(f"  Validation - Spikes (1): {y_val.sum()} ({y_val.mean()*100:.2f}%), Normal (0): {(1-y_val).sum()} ({(1-y_val.mean())*100:.2f}%)")
    logger.info(f"  Test - Spikes (1): {y_test.sum()} ({y_test.mean()*100:.2f}%), Normal (0): {(1-y_test).sum()} ({(1-y_test.mean())*100:.2f}%)")
    
    # Warn if validation or test sets have no positive labels
    if y_val.sum() == 0:
        logger.warning("WARNING: Validation set has no positive labels (spikes). Model evaluation will be limited.")
    if y_test.sum() == 0:
        logger.warning("WARNING: Test set has no positive labels (spikes). Model evaluation will be limited.")
```

**Flow:**
1. Load data and sort by timestamp
2. Split data temporally (70%/10%/20%)
3. Compute threshold τ from training data (95th percentile)
4. Create labels for all splits using the same threshold
5. Warn if validation/test have no positive labels

---

## 6. Solutions

### 6.1 Stratified Temporal Split (Already Implemented)

The code includes a `stratified_temporal_split` function that redistributes positive samples across splits while maintaining temporal order.

**How it works:**
1. Do initial temporal split
2. Create labels based on threshold
3. If val/test have no positives, redistribute some from training
4. Maintain approximate temporal order by swapping positives near split boundaries

**Configuration:**
```yaml
model:
  split_strategy: 'stratified_temporal'  # Use stratified split
  min_positive_ratio: 0.01  # 1% minimum positives in each split
```

### 6.2 Lower Threshold Percentile

Instead of 95th percentile, use 90th percentile:

```yaml
model:
  threshold_percentile: 90  # Instead of 95
```

### 6.3 Collect More Data

Collect more data over a longer time period to ensure:
- Spikes are distributed across time periods
- Validation/test periods are more representative
- More stable threshold estimation

---

## 7. Summary

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
6. **Solution:** Use stratified temporal split (already implemented)

---

## 8. Visualization

Run the visualization script to see the temporal distribution:

```bash
python scripts/visualize_split_distribution.py
```

This creates `reports/split_distribution_analysis.png` showing:
1. Temporal distribution of `future_volatility` across splits
2. Histogram of `future_volatility` by split
3. Spike locations over time

---

## 9. References

- **Code:** `models/train.py`
- **Config:** `config.yaml`
- **Visualization:** `scripts/visualize_split_distribution.py`
- **Analysis:** `scripts/analyze_label_distribution.py`
- **Detailed Doc:** `docs/train_val_test_split_analysis.md`

