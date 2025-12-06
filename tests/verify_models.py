#!/usr/bin/env python3
"""
Verify that model files exist and are loadable.
This script checks both XGBoost and Logistic Regression models.
"""

import sys
import pickle
import joblib
from pathlib import Path

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def print_success(text: str):
    """Print success message."""
    print(f"{GREEN}✓{RESET} {text}")


def print_error(text: str):
    """Print error message."""
    print(f"{RED}✗{RESET} {text}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{YELLOW}⚠{RESET} {text}")


def verify_model(model_path: Path, model_name: str) -> bool:
    """Verify a model file exists and can be loaded."""
    if not model_path.exists():
        print_error(f"{model_name}: File not found at {model_path}")
        return False

    # Check file size
    size_kb = model_path.stat().st_size / 1024
    if size_kb < 1:
        print_error(f"{model_name}: File is too small ({size_kb:.2f} KB)")
        return False

    print(f"  Found {model_name} ({size_kb:.1f} KB)")

    # Try to load the model
    try:
        # Try joblib first (most common)
        try:
            model = joblib.load(model_path)
            print_success(f"{model_name}: Loaded successfully with joblib")
        except Exception:
            # Fallback to pickle
            with open(model_path, "rb") as f:
                model = pickle.load(f)
            print_success(f"{model_name}: Loaded successfully with pickle")

        # Verify model has predict_proba method (for ML models)
        if hasattr(model, "predict_proba"):
            # Test with dummy data
            import numpy as np

            try:
                # Get feature count from model
                if hasattr(model, "n_features_in_"):
                    n_features = model.n_features_in_
                elif hasattr(model, "feature_names_in_"):
                    n_features = len(model.feature_names_in_)
                else:
                    # Default to 7 features (as per API)
                    n_features = 7

                dummy_X = np.random.rand(1, n_features)
                predictions = model.predict_proba(dummy_X)
                if predictions.shape[1] >= 2:
                    print_success(f"{model_name}: Can make predictions (probabilities)")
                else:
                    print_warning(
                        f"{model_name}: predict_proba returns unexpected shape"
                    )
            except Exception as e:
                print_warning(f"{model_name}: Could not test predictions: {e}")

        return True

    except Exception as e:
        print_error(f"{model_name}: Failed to load - {e}")
        return False


def main():
    """Main function to verify all models."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    artifacts_dir = project_root / "models" / "artifacts"

    print("Verifying model files...")
    print(f"Artifacts directory: {artifacts_dir}\n")

    if not artifacts_dir.exists():
        print_error(f"Artifacts directory does not exist: {artifacts_dir}")
        return 1

    all_passed = True

    # Verify XGBoost model
    xgb_path = artifacts_dir / "xgb_model.pkl"
    if not verify_model(xgb_path, "XGBoost Model"):
        all_passed = False

    print()

    # Verify Logistic Regression model
    logistic_path = artifacts_dir / "logistic_model.pkl"
    if not verify_model(logistic_path, "Logistic Regression Model"):
        all_passed = False

    print()

    # Summary
    if all_passed:
        print_success("All models verified successfully!")
        return 0
    else:
        print_error("Some models failed verification")
        return 1


if __name__ == "__main__":
    sys.exit(main())
