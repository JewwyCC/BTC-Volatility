# Feature Specification Document

**Date:** November 12, 2025  
**Project:** Real-Time Crypto Volatility Detection

---

## 1. Target Horizon

**Prediction Horizon:** 60 seconds

The model predicts whether a volatility spike will occur in the next 60 seconds based on current and historical market features.

---

## 2. Volatility Proxy

**Definition:** Rolling standard deviation of midprice returns over the next horizon (60 seconds)

**Formula:**
```
σ_future = std(returns[t : t+60s])
```

Where:
- `returns` = log returns of midprice: `log(midprice[t] / midprice[t-1])`
- `midprice` = (best_bid + best_ask) / 2
- The standard deviation is computed over a rolling 60-second window looking forward

**Rationale:**
- Standard deviation of returns is a standard measure of volatility in finance
- Using log returns makes the measure scale-invariant
- 60-second horizon balances between:
  - Short enough to be actionable for trading/risk management
  - Long enough to capture meaningful volatility patterns

---

## 3. Label Definition

**Binary Classification:**
```
Label = 1 if σ_future >= τ
Label = 0 if σ_future < τ
```

Where:
- `σ_future` = future volatility (rolling std of returns over next 60s)
- `τ` = threshold value (see below)

---

## 4. Chosen Threshold (τ)

**Value:** `τ = 0.000036` (approximately)

**Percentile:** 95th percentile of future volatility distribution

**Justification:**

The threshold was selected based on percentile analysis of the training data:

1. **Percentile Analysis:**
   - 50th percentile: Baseline volatility
   - 75th percentile: Moderate increase
   - 90th percentile: Elevated volatility
   - **95th percentile: High volatility (selected threshold)**
   - 99th percentile: Extreme volatility

2. **Rationale for 95th Percentile:**
   - **Sufficient Positive Examples:** Captures ~5% of samples as volatility spikes, providing enough positive examples for model training
   - **Balanced Classification:** Avoids extreme class imbalance while still identifying meaningful volatility events
   - **Actionable Threshold:** Events above this threshold represent significant volatility increases that warrant attention
   - **Clear Separation:** Percentile plots show clear separation between normal and spike events at this level

3. **Label Distribution:**
   - Volatility Spike (1): ~5% of samples
   - Normal (0): ~95% of samples
   - This distribution is suitable for imbalanced classification techniques

**Note:** The exact threshold value should be determined by running the EDA notebook (`notebooks/eda.ipynb`) on your specific dataset, as it may vary based on:
- Trading pair (BTC-USD vs ETH-USD, etc.)
- Market conditions during data collection
- Time period of data

---

## 5. Feature Definitions

### 5.1 Core Features

#### Midprice Returns
- **Definition:** Log returns of midprice
- **Formula:** `log(midprice[t] / midprice[t-1])`
- **Window:** Point-in-time (no window)
- **Purpose:** Captures price movement direction and magnitude

#### Bid-Ask Spread
- **Definition:** Relative bid-ask spread
- **Formula:** `(best_ask - best_bid) / midprice`
- **Window:** Point-in-time
- **Purpose:** Measures market liquidity and transaction costs

#### Trade Intensity
- **Definition:** Number of ticks per second
- **Formula:** `count(ticks in window) / window_size`
- **Window:** Rolling 60-second window
- **Purpose:** Measures market activity and information flow

#### Order Book Imbalance
- **Definition:** Normalized difference between bid and ask quantities
- **Formula:** `(best_bid_quantity - best_ask_quantity) / (best_bid_quantity + best_ask_quantity)`
- **Range:** [-1, 1], where -1 = all ask, +1 = all bid, 0 = balanced
- **Window:** Point-in-time
- **Purpose:** Indicates market pressure direction (buying vs selling pressure)

### 5.2 Rolling Window Features

All rolling features use a 60-second window (aligned with prediction horizon).

#### Rolling Standard Deviation of Returns
- **Definition:** Standard deviation of midprice returns over rolling window
- **Window:** 60 seconds
- **Purpose:** Measures recent volatility, directly related to target variable

#### Rolling Mean Spread
- **Definition:** Average bid-ask spread over rolling window
- **Window:** 60 seconds
- **Purpose:** Captures sustained liquidity conditions

#### Rolling Mean Order Book Imbalance
- **Definition:** Average order book imbalance over rolling window
- **Window:** 60 seconds
- **Purpose:** Captures sustained market pressure direction

---

## 6. Feature Engineering Pipeline

### 6.1 Data Flow

```
Raw Ticker Data (Kafka: ticks.raw)
    ↓
Parse & Extract Fields
    ↓
Compute Point-in-Time Features
    ↓
Apply Rolling Windows (60s)
    ↓
Compute Future Volatility (60s forward)
    ↓
Create Binary Labels (σ_future >= τ)
    ↓
Feature DataFrame (Kafka: ticks.features + Parquet)
```

### 6.2 Processing Details

1. **Message Parsing:**
   - Extract ticker data from Coinbase WebSocket messages
   - Handle both "snapshot" and "update" message types
   - Parse timestamps and numeric fields

2. **Feature Computation:**
   - Sort by timestamp
   - Compute midprice from best_bid and best_ask
   - Calculate returns, spreads, and imbalances
   - Apply rolling window aggregations

3. **Future Volatility:**
   - Shift returns forward
   - Compute rolling std over 60-second window
   - This becomes the target variable

4. **Label Creation:**
   - Compare future_volatility to threshold τ
   - Create binary labels (0 or 1)

---

## 7. Data Quality Considerations

### 7.1 Missing Data
- **Handling:** Forward-fill for missing ticks within reasonable time windows
- **Outliers:** Cap extreme values at 99.9th percentile to prevent model instability

### 7.2 Temporal Alignment
- **Timestamps:** All features aligned to tick timestamps
- **Rolling Windows:** Use time-based windows (not count-based) for consistency

### 7.3 Reproducibility
- **Replay Script:** `scripts/replay.py` regenerates features identically from raw data
- **Deterministic:** All operations are deterministic (no random seeds in feature computation)

---

## 8. Feature Statistics (Example)

Based on initial data collection:

| Feature | Mean | Std | Min | Max |
|---------|------|-----|-----|-----|
| midprice_returns | ~0.000001 | ~0.0001 | -0.01 | 0.01 |
| bid_ask_spread | ~0.0001 | ~0.00005 | 0.0 | 0.001 |
| trade_intensity | ~0.1 | ~0.05 | 0.0 | 0.5 |
| order_book_imbalance | ~0.0 | ~0.3 | -1.0 | 1.0 |
| rolling_std_returns | ~0.00003 | ~0.00001 | 0.0 | 0.0001 |
| future_volatility | ~0.000028 | ~0.000006 | 0.0 | 0.000049 |

*Note: Actual values will vary based on market conditions and data collection period.*

---

## 9. References

- **Config File:** `config.yaml` (feature window sizes and horizons)
- **Feature Code:** `features/featurizer.py`
- **Replay Script:** `scripts/replay.py`
- **EDA Notebook:** `notebooks/eda.ipynb`

---

**Status:** ✓ Complete for Milestone 2

