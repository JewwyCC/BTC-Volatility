#!/usr/bin/env python3
"""
Generate Model Evaluation Report

Creates a comprehensive evaluation report with PR-AUC and other metrics
for both baseline and ML models.
"""

import argparse
import logging
from pathlib import Path
from datetime import datetime

import numpy as np
import yaml
import mlflow
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_config():
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def format_metric(value, default="N/A"):
    """Format metric value, handling NaN."""
    if value is None or (isinstance(value, (int, float)) and np.isnan(value)):
        return default
    return f"{value:.4f}"


def generate_report_text(
    metrics_baseline: dict, metrics_ml: dict, model_type: str = "logistic"
) -> str:
    """Generate markdown report text."""
    report = f"""# Model Evaluation Report

**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Project:** Real-Time Crypto Volatility Detection

---

## Executive Summary

This report evaluates two models for predicting volatility spikes:
1. **Baseline Model**: Z-score rule based on rolling standard deviation of returns
2. **ML Model**: {model_type.upper()} classifier

Both models were evaluated on validation and test sets using time-based splits.

---

## Evaluation Metrics

### Primary Metric: PR-AUC (Precision-Recall Area Under Curve)

PR-AUC is the required metric for this project, as it is more informative than ROC-AUC for imbalanced classification problems.

#### Baseline Model
- **Validation PR-AUC:** {metrics_baseline.get('val_pr_auc', 0):.4f}
- **Test PR-AUC:** {metrics_baseline.get('test_pr_auc', 0):.4f}

#### ML Model ({model_type.upper()})
- **Validation PR-AUC:** {metrics_ml.get('val_pr_auc', 0):.4f}
- **Test PR-AUC:** {metrics_ml.get('test_pr_auc', 0):.4f}

**Best Model:** {"ML Model" if metrics_ml.get('test_pr_auc', 0) > metrics_baseline.get('test_pr_auc', 0) else "Baseline Model"}

---

## Detailed Metrics

### Baseline Model

#### Validation Set
- PR-AUC: {metrics_baseline.get('val_pr_auc', 0):.4f}
- ROC-AUC: {format_metric(metrics_baseline.get('val_roc_auc', 0))}
- F1 Score: {metrics_baseline.get('val_f1', 0):.4f}
- Precision: {metrics_baseline.get('val_precision', 0):.4f}
- Recall: {metrics_baseline.get('val_recall', 0):.4f}

#### Test Set
- PR-AUC: {metrics_baseline.get('test_pr_auc', 0):.4f}
- ROC-AUC: {format_metric(metrics_baseline.get('test_roc_auc', 0))}
- F1 Score: {metrics_baseline.get('test_f1', 0):.4f}
- Precision: {metrics_baseline.get('test_precision', 0):.4f}
- Recall: {metrics_baseline.get('test_recall', 0):.4f}

### ML Model ({model_type.upper()})

#### Validation Set
- PR-AUC: {metrics_ml.get('val_pr_auc', 0):.4f}
- ROC-AUC: {format_metric(metrics_ml.get('val_roc_auc', 0))}
- F1 Score: {metrics_ml.get('val_f1', 0):.4f}
- Precision: {metrics_ml.get('val_precision', 0):.4f}
- Recall: {metrics_ml.get('val_recall', 0):.4f}

#### Test Set
- PR-AUC: {metrics_ml.get('test_pr_auc', 0):.4f}
- ROC-AUC: {format_metric(metrics_ml.get('test_roc_auc', 0))}
- F1 Score: {metrics_ml.get('test_f1', 0):.4f}
- Precision: {metrics_ml.get('test_precision', 0):.4f}
- Recall: {metrics_ml.get('test_recall', 0):.4f}

---

## Confusion Matrices

### Baseline Model - Test Set
- True Positives: {metrics_baseline.get('test_true_positives', 0)}
- False Positives: {metrics_baseline.get('test_false_positives', 0)}
- True Negatives: {metrics_baseline.get('test_true_negatives', 0)}
- False Negatives: {metrics_baseline.get('test_false_negatives', 0)}

### ML Model - Test Set
- True Positives: {metrics_ml.get('test_true_positives', 0)}
- False Positives: {metrics_ml.get('test_false_positives', 0)}
- True Negatives: {metrics_ml.get('test_true_negatives', 0)}
- False Negatives: {metrics_ml.get('test_false_negatives', 0)}

---

## Model Comparison

| Metric | Baseline | ML Model | Winner |
|--------|----------|----------|--------|
| Test PR-AUC | {metrics_baseline.get('test_pr_auc', 0):.4f} | {metrics_ml.get('test_pr_auc', 0):.4f} | {"ML Model" if metrics_ml.get('test_pr_auc', 0) > metrics_baseline.get('test_pr_auc', 0) else "Baseline"} |
| Test F1 | {metrics_baseline.get('test_f1', 0):.4f} | {metrics_ml.get('test_f1', 0):.4f} | {"ML Model" if metrics_ml.get('test_f1', 0) > metrics_baseline.get('test_f1', 0) else "Baseline"} |
| Test Precision | {metrics_baseline.get('test_precision', 0):.4f} | {metrics_ml.get('test_precision', 0):.4f} | {"ML Model" if metrics_ml.get('test_precision', 0) > metrics_baseline.get('test_precision', 0) else "Baseline"} |
| Test Recall | {metrics_baseline.get('test_recall', 0):.4f} | {metrics_ml.get('test_recall', 0):.4f} | {"ML Model" if metrics_ml.get('test_recall', 0) > metrics_baseline.get('test_recall', 0) else "Baseline"} |

---

## Conclusions

1. **PR-AUC Performance**: {"ML model shows better PR-AUC" if metrics_ml.get('test_pr_auc', 0) > metrics_baseline.get('test_pr_auc', 0) else "Baseline model shows better PR-AUC"} on the test set.

2. **Model Selection**: Based on PR-AUC (the primary metric), the **{"ML Model" if metrics_ml.get('test_pr_auc', 0) > metrics_baseline.get('test_pr_auc', 0) else "Baseline Model"}** is recommended for production use.

3. **Performance Notes**: 
   - Both models were evaluated on time-based splits to prevent data leakage
   - The imbalanced nature of the problem (5% positive class) makes PR-AUC the appropriate metric
   - Further tuning may improve performance

---

## Recommendations

1. **Model Deployment**: Deploy the {"ML Model" if metrics_ml.get('test_pr_auc', 0) > metrics_baseline.get('test_pr_auc', 0) else "Baseline Model"} for production use.

2. **Monitoring**: Set up monitoring for:
   - Prediction latency (target: < 2x real-time)
   - Model performance over time
   - Data drift detection

3. **Future Improvements**:
   - Collect more training data
   - Experiment with different model architectures
   - Tune hyperparameters
   - Consider ensemble methods

---

**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    return report


def main():
    parser = argparse.ArgumentParser(description="Generate model evaluation report")
    parser.add_argument(
        "--mlflow_uri",
        type=str,
        default="http://localhost:5001",
        help="MLflow tracking URI",
    )
    parser.add_argument(
        "--experiment_name",
        type=str,
        default="volatility_detection",
        help="MLflow experiment name",
    )
    parser.add_argument(
        "--output", type=str, default="reports/model_eval.md", help="Output report file"
    )
    parser.add_argument("--config", type=str, default=None, help="Path to config file")

    args = parser.parse_args()

    # Load configuration
    if args.config:
        with open(args.config, "r") as f:
            yaml.safe_load(f)
    else:
        load_config()

    # Connect to MLflow
    mlflow.set_tracking_uri(args.mlflow_uri)

    try:
        experiment = mlflow.get_experiment_by_name(args.experiment_name)
        if experiment is None:
            logger.error(f"Experiment '{args.experiment_name}' not found")
            return 1

        # Get latest runs
        runs = mlflow.search_runs(
            experiment_ids=[experiment.experiment_id],
            order_by=["start_time desc"],
            max_results=10,
        )

        if len(runs) == 0:
            logger.error("No runs found in experiment")
            return 1

        # Find baseline and ML model runs
        baseline_run = None
        ml_run = None

        for _, run in runs.iterrows():
            run_name = run.get("tags.mlflow.runName", "")
            if "baseline" in run_name.lower():
                baseline_run = run
            elif "ml_model" in run_name.lower():
                ml_run = run

        if baseline_run is None:
            logger.warning("Baseline run not found, using first run")
            baseline_run = runs.iloc[0]

        if ml_run is None:
            logger.warning("ML model run not found, using second run")
            if len(runs) > 1:
                ml_run = runs.iloc[1]
            else:
                ml_run = baseline_run

        # Extract metrics
        metrics_baseline = {
            "val_pr_auc": baseline_run.get("metrics.val_pr_auc", 0),
            "test_pr_auc": baseline_run.get("metrics.test_pr_auc", 0),
            "val_roc_auc": baseline_run.get("metrics.val_roc_auc", 0),
            "test_roc_auc": baseline_run.get("metrics.test_roc_auc", 0),
            "val_f1": baseline_run.get("metrics.val_f1", 0),
            "test_f1": baseline_run.get("metrics.test_f1", 0),
            "val_precision": baseline_run.get("metrics.val_precision", 0),
            "test_precision": baseline_run.get("metrics.test_precision", 0),
            "val_recall": baseline_run.get("metrics.val_recall", 0),
            "test_recall": baseline_run.get("metrics.test_recall", 0),
            "test_true_positives": int(
                baseline_run.get("metrics.test_true_positives", 0)
            ),
            "test_false_positives": int(
                baseline_run.get("metrics.test_false_positives", 0)
            ),
            "test_true_negatives": int(
                baseline_run.get("metrics.test_true_negatives", 0)
            ),
            "test_false_negatives": int(
                baseline_run.get("metrics.test_false_negatives", 0)
            ),
        }

        metrics_ml = {
            "val_pr_auc": ml_run.get("metrics.val_pr_auc", 0),
            "test_pr_auc": ml_run.get("metrics.test_pr_auc", 0),
            "val_roc_auc": ml_run.get("metrics.val_roc_auc", 0),
            "test_roc_auc": ml_run.get("metrics.test_roc_auc", 0),
            "val_f1": ml_run.get("metrics.val_f1", 0),
            "test_f1": ml_run.get("metrics.test_f1", 0),
            "val_precision": ml_run.get("metrics.val_precision", 0),
            "test_precision": ml_run.get("metrics.test_precision", 0),
            "val_recall": ml_run.get("metrics.val_recall", 0),
            "test_recall": ml_run.get("metrics.test_recall", 0),
            "test_true_positives": int(ml_run.get("metrics.test_true_positives", 0)),
            "test_false_positives": int(ml_run.get("metrics.test_false_positives", 0)),
            "test_true_negatives": int(ml_run.get("metrics.test_true_negatives", 0)),
            "test_false_negatives": int(ml_run.get("metrics.test_false_negatives", 0)),
        }

        # Get model type
        model_type = ml_run.get("params.model_type", "logistic")

        # Generate report
        report_text = generate_report_text(metrics_baseline, metrics_ml, model_type)

        # Save report
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(report_text)

        logger.info(f"✓ Evaluation report saved to {output_path}")

        # Also save as PDF if markdown is available
        try:
            import markdown
            from weasyprint import HTML

            html = markdown.markdown(report_text)
            pdf_path = output_path.with_suffix(".pdf")
            HTML(string=html).write_pdf(pdf_path)
            logger.info(f"✓ PDF report saved to {pdf_path}")
        except ImportError:
            logger.info("PDF generation skipped (markdown/weasyprint not available)")

    except Exception as e:
        logger.error(f"Error generating report: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
