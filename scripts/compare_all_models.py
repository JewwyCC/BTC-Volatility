#!/usr/bin/env python3
"""
Compare all model variants: Logistic, XGBoost, and XGBoost with calibration.
"""

import subprocess
import sys
from pathlib import Path

def run_training(model_type, calibrate=False):
    """Run training for a specific model configuration."""
    cmd = [
        sys.executable, 
        "models/train.py",
        "--features", "data/processed/features.parquet",
        "--model_type", model_type
    ]
    if calibrate:
        cmd.append("--calibrate")
    
    print(f"\n{'='*60}")
    print(f"Training: {model_type}{' (calibrated)' if calibrate else ''}")
    print(f"{'='*60}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"ERROR: Training failed")
        print(result.stderr)
        return None
    
    # Extract key metrics from output
    output = result.stdout
    metrics = {}
    
    # Extract test metrics
    for line in output.split('\n'):
        if 'ML-' in line and 'TEST Metrics:' in line:
            # Next lines will have metrics
            continue
        if 'PR-AUC:' in line and 'TEST' in output.split('\n')[output.split('\n').index(line)-1] if 'TEST' in output else False:
            try:
                metrics['pr_auc'] = float(line.split('PR-AUC:')[1].strip())
            except:
                pass
        if 'ROC-AUC:' in line and 'TEST' in output.split('\n')[output.split('\n').index(line)-1] if 'TEST' in output else False:
            try:
                metrics['roc_auc'] = float(line.split('ROC-AUC:')[1].strip().split()[0])
            except:
                pass
        if 'F1 Score:' in line and 'TEST' in output.split('\n')[output.split('\n').index(line)-1] if 'TEST' in output else False:
            try:
                metrics['f1'] = float(line.split('F1 Score:')[1].strip())
            except:
                pass
        if 'Precision:' in line and 'TEST' in output.split('\n')[output.split('\n').index(line)-1] if 'TEST' in output else False:
            try:
                metrics['precision'] = float(line.split('Precision:')[1].strip())
            except:
                pass
        if 'Recall:' in line and 'TEST' in output.split('\n')[output.split('\n').index(line)-1] if 'TEST' in output else False:
            try:
                metrics['recall'] = float(line.split('Recall:')[1].strip())
            except:
                pass
    
    return metrics

def main():
    """Compare all model variants."""
    print("Model Comparison Script")
    print("="*60)
    
    results = {}
    
    # Test Logistic Regression
    print("\n1. Testing Logistic Regression...")
    results['logistic'] = run_training('logistic')
    
    # Test XGBoost
    print("\n2. Testing XGBoost...")
    results['xgboost'] = run_training('xgboost')
    
    # Test XGBoost with calibration
    print("\n3. Testing XGBoost (calibrated)...")
    results['xgboost_calibrated'] = run_training('xgboost', calibrate=True)
    
    # Print summary
    print("\n" + "="*60)
    print("COMPARISON SUMMARY")
    print("="*60)
    
    for model_name, metrics in results.items():
        if metrics:
            print(f"\n{model_name.upper()}:")
            print(f"  F1 Score: {metrics.get('f1', 'N/A'):.4f}")
            print(f"  ROC-AUC: {metrics.get('roc_auc', 'N/A'):.4f}")
            print(f"  PR-AUC: {metrics.get('pr_auc', 'N/A'):.4f}")
            print(f"  Precision: {metrics.get('precision', 'N/A'):.4f}")
            print(f"  Recall: {metrics.get('recall', 'N/A'):.4f}")

if __name__ == "__main__":
    main()

