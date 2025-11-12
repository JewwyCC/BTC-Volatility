#!/usr/bin/env python3
"""Analyze label distribution across different thresholds and split strategies."""

import pandas as pd
import numpy as np

# Load data
df = pd.read_parquet('data/processed/features.parquet')
df = df.sort_values('timestamp').reset_index(drop=True)

print("=" * 60)
print("LABEL DISTRIBUTION ANALYSIS")
print("=" * 60)

print(f"\nTotal samples: {len(df)}")

# Analyze different percentile thresholds
print("\n" + "=" * 60)
print("PERCENTILE THRESHOLD ANALYSIS")
print("=" * 60)
for p in [85, 90, 95]:
    tau = df['future_volatility'].quantile(p/100)
    count = (df['future_volatility'] >= tau).sum()
    print(f"{p}th percentile: tau={tau:.8f}, positives={count} ({count/len(df)*100:.2f}%)")

# Analyze temporal split with 95th percentile
print("\n" + "=" * 60)
print("TEMPORAL SPLIT ANALYSIS (95th percentile threshold)")
print("=" * 60)
n_train = int(len(df) * 0.7)
n_val = int(len(df) * 0.1)
tau = df['future_volatility'].quantile(0.95)

train_pos = (df.iloc[:n_train]['future_volatility'] >= tau).sum()
val_pos = (df.iloc[n_train:n_train+n_val]['future_volatility'] >= tau).sum()
test_pos = (df.iloc[n_train+n_val:]['future_volatility'] >= tau).sum()

print(f"Train: {train_pos} positives ({train_pos/n_train*100:.2f}%)")
print(f"Val: {val_pos} positives ({val_pos/n_val*100:.2f}%)")
print(f"Test: {test_pos} positives ({test_pos/(len(df)-n_train-n_val)*100:.2f}%)")

# Analyze temporal split with 90th percentile
print("\n" + "=" * 60)
print("TEMPORAL SPLIT ANALYSIS (90th percentile threshold)")
print("=" * 60)
tau_90 = df['future_volatility'].quantile(0.90)
train_pos_90 = (df.iloc[:n_train]['future_volatility'] >= tau_90).sum()
val_pos_90 = (df.iloc[n_train:n_train+n_val]['future_volatility'] >= tau_90).sum()
test_pos_90 = (df.iloc[n_train+n_val:]['future_volatility'] >= tau_90).sum()

print(f"Train: {train_pos_90} positives ({train_pos_90/n_train*100:.2f}%)")
print(f"Val: {val_pos_90} positives ({val_pos_90/n_val*100:.2f}%)")
print(f"Test: {test_pos_90} positives ({test_pos_90/(len(df)-n_train-n_val)*100:.2f}%)")

# Analyze temporal split with 85th percentile
print("\n" + "=" * 60)
print("TEMPORAL SPLIT ANALYSIS (85th percentile threshold)")
print("=" * 60)
tau_85 = df['future_volatility'].quantile(0.85)
train_pos_85 = (df.iloc[:n_train]['future_volatility'] >= tau_85).sum()
val_pos_85 = (df.iloc[n_train:n_train+n_val]['future_volatility'] >= tau_85).sum()
test_pos_85 = (df.iloc[n_train+n_val:]['future_volatility'] >= tau_85).sum()

print(f"Train: {train_pos_85} positives ({train_pos_85/n_train*100:.2f}%)")
print(f"Val: {val_pos_85} positives ({val_pos_85/n_val*100:.2f}%)")
print(f"Test: {test_pos_85} positives ({test_pos_85/(len(df)-n_train-n_val)*100:.2f}%)")

