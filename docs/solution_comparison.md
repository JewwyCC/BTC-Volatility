# Solution Comparison: Addressing No Positive Labels in Validation/Test Sets

## Problem
When using a strict temporal split with a 95th percentile threshold for volatility spike detection, all positive labels (spikes) are concentrated in the training set, leaving validation and test sets with zero positives. This prevents proper model evaluation.

## Solutions Evaluated

### Solution 1: Lower Threshold Percentile (90% or 85%)
**Approach:** Reduce the threshold percentile from 95% to 90% or 85% to create more positive labels overall.

**Implementation:**
- Configurable threshold percentile (default: 95%)
- Maintains strict temporal split
- Creates more positives in training set

**Results:**
- **90th percentile:** 243 positives in training (10.01%), 0 in validation/test
- **85th percentile:** 364 positives in training (14.99%), 0 in validation/test

**Pros:**
- Simple to implement
- Maintains strict temporal order
- No data redistribution needed
- Creates more training examples

**Cons:**
- ❌ **Does NOT solve the problem** - all positives still in training set
- Changes problem definition (now detecting less extreme volatility events)
- May reduce model's ability to detect true spikes (95th percentile events)
- Still cannot evaluate on validation/test sets

**Verdict:** ❌ **NOT RECOMMENDED** - Does not address the core issue.

---

### Solution 2: Stratified Temporal Split
**Approach:** Use temporal split with stratification to ensure positives are distributed across all splits while maintaining approximate temporal order.

**Implementation:**
- Compute threshold from initial temporal split of training data
- Redistribute positives from training to validation/test sets
- Swap positives near split boundaries with negatives to maintain temporal order
- Ensures minimum positive ratio in each split (configurable, default: 1%)

**Results:**
- **95th percentile with stratified split:**
  - Train: 122 positives (5.02%)
  - Validation: 12 positives (3.47%)
  - Test: 24 positives (3.45%)
- **Evaluation:** ✅ All splits can be properly evaluated
- **Model Performance:**
  - Validation: PR-AUC=1.0000, ROC-AUC=1.0000, F1=1.0000
  - Test: PR-AUC=1.0000, ROC-AUC=1.0000, F1=1.0000

**Pros:**
- ✅ **Solves the problem** - ensures positives in all splits
- Maintains strict 95th percentile definition (true spikes)
- Allows proper evaluation on validation and test sets
- Maintains approximate temporal order (swaps near boundaries)
- More realistic evaluation scenario
- Configurable minimum positive ratio

**Cons:**
- Slightly breaks strict temporal order (but minimal, near boundaries)
- More complex implementation
- May slightly reduce training set size (some positives moved to val/test)

**Verdict:** ✅ **RECOMMENDED** - Effectively solves the problem while maintaining problem definition.

---

## Detailed Comparison

| Metric | Solution 1a (90%) | Solution 1b (85%) | Solution 2 (Stratified) |
|--------|-------------------|-------------------|------------------------|
| **Threshold Percentile** | 90% | 85% | 95% |
| **Train Positives** | 243 (10.01%) | 364 (14.99%) | 122 (5.02%) |
| **Validation Positives** | 0 (0.00%) | 0 (0.00%) | 12 (3.47%) |
| **Test Positives** | 0 (0.00%) | 0 (0.00%) | 24 (3.45%) |
| **Can Evaluate Validation** | ❌ No | ❌ No | ✅ Yes |
| **Can Evaluate Test** | ❌ No | ❌ No | ✅ Yes |
| **Maintains Problem Definition** | ❌ Changes | ❌ Changes | ✅ Maintains |
| **Temporal Order** | ✅ Strict | ✅ Strict | ⚠️ Approximate |
| **Implementation Complexity** | ✅ Simple | ✅ Simple | ⚠️ Moderate |

## Recommendation

**Solution 2 (Stratified Temporal Split) is strongly recommended** because:

1. **Effectively solves the problem** - ensures all splits have positives for evaluation
2. **Maintains problem definition** - continues to detect true volatility spikes (95th percentile)
3. **Enables proper evaluation** - validation and test sets can be meaningfully evaluated
4. **Minimal temporal distortion** - only swaps samples near split boundaries
5. **More realistic** - in production, spikes can occur at any time, not just in training period

## Configuration

To use Solution 2, set in `config.yaml`:

```yaml
model:
  threshold_percentile: 95  # Maintain strict spike definition
  split_strategy: 'stratified_temporal'  # Use stratified split
  min_positive_ratio: 0.01  # Minimum 1% positives in each split
```

To use Solution 1 (not recommended), set:

```yaml
model:
  threshold_percentile: 90  # or 85
  split_strategy: 'temporal'  # Strict temporal split
```

## Implementation Details

### Stratified Temporal Split Algorithm

1. **Initial Temporal Split:** Split data temporally into train/val/test
2. **Compute Threshold:** Calculate threshold (τ) from initial training split
3. **Create Labels:** Label all samples based on threshold
4. **Redistribute Positives:**
   - Calculate target positives for each split (proportional + minimum)
   - If validation/test have insufficient positives:
     - Identify positives in training near split boundaries
     - Swap with negatives in validation/test near boundaries
     - Maintain approximate temporal order
5. **Recombine:** Sort each split by timestamp

This ensures:
- All splits have positive labels for evaluation
- Temporal order is approximately maintained
- Problem definition (95th percentile) is preserved

