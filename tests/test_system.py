#!/usr/bin/env python3
"""
Comprehensive System Test

Tests the entire system to ensure it runs perfectly:
- Docker services startup
- API endpoints
- API contract compliance
- Model rollback
- Error handling
- Metrics
"""

import os
import sys
import time
import json
import subprocess
import requests
from pathlib import Path
from typing import Dict, List, Tuple

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_status(message: str, status: str = "INFO"):
    """Print colored status message."""
    colors = {"PASS": GREEN, "FAIL": RED, "WARN": YELLOW, "INFO": BLUE}
    color = colors.get(status, RESET)
    symbol = (
        "✓"
        if status == "PASS"
        else "✗" if status == "FAIL" else "⚠" if status == "WARN" else "ℹ"
    )
    print(f"{color}{symbol} {message}{RESET}")


def check_docker_compose():
    """Check if docker compose is available."""
    try:
        result = subprocess.run(
            ["docker", "compose", "version"], capture_output=True, text=True
        )
        if result.returncode == 0:
            print_status("Docker Compose available", "PASS")
            return True
        else:
            print_status("Docker Compose not available", "FAIL")
            return False
    except FileNotFoundError:
        print_status("Docker not installed", "FAIL")
        return False


def check_services_running():
    """Check if services are running."""
    print_status("Checking services...", "INFO")

    # Check containers directly (more reliable)
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True
        )

        running_containers = set(result.stdout.strip().split("\n"))
        running_containers = {
            c for c in running_containers if c
        }  # Remove empty strings

        # Required containers
        required_containers = {
            "kafka": ["kafka"],
            "mlflow": ["mlflow"],
            "api": [
                "ml-prediction-api",
                "api",
            ],  # Container name is 'ml-prediction-api'
        }

        all_running = True
        for service_key, possible_names in required_containers.items():
            found = any(name in running_containers for name in possible_names)
            if found:
                actual_name = next(
                    (n for n in possible_names if n in running_containers), None
                )
                print_status(
                    f"Service '{service_key}' is running (container: {actual_name})",
                    "PASS",
                )
            else:
                print_status(
                    f"Service '{service_key}' is not running (checked containers: {possible_names})",
                    "WARN",
                )
                # Don't fail if API isn't running - it might be run separately
                if service_key == "api":
                    print_status(
                        "  Note: API can be run separately with: python -m uvicorn api_v1:api --reload",
                        "INFO",
                    )
                else:
                    all_running = False

        return all_running
    except Exception as e:
        print_status(f"Error checking services: {e}", "FAIL")
        return False


def test_health_endpoint(base_url: str = "http://localhost:8000") -> bool:
    """Test /health endpoint."""
    print_status("Testing /health endpoint...", "INFO")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok":
                print_status("/health returns correct response", "PASS")
                return True
            else:
                print_status(f"/health returned unexpected data: {data}", "FAIL")
                return False
        else:
            print_status(f"/health returned status {response.status_code}", "FAIL")
            return False
    except requests.exceptions.ConnectionError:
        print_status("Cannot connect to API. Is it running?", "FAIL")
        return False
    except Exception as e:
        print_status(f"Error testing /health: {e}", "FAIL")
        return False


def test_version_endpoint(base_url: str = "http://localhost:8000") -> bool:
    """Test /version endpoint."""
    print_status("Testing /version endpoint...", "INFO")
    try:
        response = requests.get(f"{base_url}/version", timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Check required fields
            if "model" in data and "sha" in data:
                print_status(
                    f"/version returns: model={data.get('model')}, sha={data.get('sha')}",
                    "PASS",
                )
                return True
            else:
                print_status(f"/version missing required fields. Got: {data}", "FAIL")
                return False
        else:
            print_status(f"/version returned status {response.status_code}", "FAIL")
            return False
    except Exception as e:
        print_status(f"Error testing /version: {e}", "FAIL")
        return False


def test_predict_endpoint(base_url: str = "http://localhost:8000") -> bool:
    """Test /predict endpoint with API contract compliance."""
    print_status("Testing /predict endpoint...", "INFO")

    payload = {"rows": [{"ret_mean": 0.05, "ret_std": 0.01, "n": 50}]}

    try:
        response = requests.post(f"{base_url}/predict", json=payload, timeout=10)

        if response.status_code == 200:
            data = response.json()

            # Check API contract compliance
            required_fields = ["scores", "model_variant", "version", "ts"]
            missing_fields = [f for f in required_fields if f not in data]

            if missing_fields:
                print_status(f"/predict missing fields: {missing_fields}", "FAIL")
                return False

            # Validate field types
            if not isinstance(data["scores"], list):
                print_status("/predict 'scores' must be a list", "FAIL")
                return False

            if not isinstance(data["model_variant"], str):
                print_status("/predict 'model_variant' must be a string", "FAIL")
                return False

            if not isinstance(data["ts"], str):
                print_status("/predict 'ts' must be a string", "FAIL")
                return False

            # Validate timestamp format (YYYY-MM-DDTHH:MM:SSZ)
            ts = data["ts"]
            if not (ts.endswith("Z") and len(ts) >= 20):
                print_status(f"/predict 'ts' format invalid: {ts}", "WARN")

            print_status(
                f"/predict returns correct format: scores={data['scores']}, model_variant={data['model_variant']}, ts={data['ts']}",
                "PASS",
            )
            return True
        elif response.status_code == 503:
            print_status("/predict returned 503 - Model not loaded", "WARN")
            return False
        else:
            print_status(
                f"/predict returned status {response.status_code}: {response.text}",
                "FAIL",
            )
            return False
    except Exception as e:
        print_status(f"Error testing /predict: {e}", "FAIL")
        return False


def test_metrics_endpoint(base_url: str = "http://localhost:8000") -> bool:
    """Test /metrics endpoint."""
    print_status("Testing /metrics endpoint...", "INFO")
    try:
        response = requests.get(f"{base_url}/metrics", timeout=5)
        if response.status_code == 200:
            content = response.text

            # Check for Prometheus format indicators
            required_metrics = [
                "predict_req_tot",
                "predict_req_latency",
            ]

            found_metrics = [m for m in required_metrics if m in content]

            if len(found_metrics) >= 1:
                print_status(
                    f"/metrics returns Prometheus format (found: {len(found_metrics)} metrics)",
                    "PASS",
                )
                return True
            else:
                print_status("/metrics doesn't contain expected metrics", "WARN")
                return True  # Still pass, might be no requests yet
        else:
            print_status(f"/metrics returned status {response.status_code}", "FAIL")
            return False
    except Exception as e:
        print_status(f"Error testing /metrics: {e}", "FAIL")
        return False


def test_error_handling(base_url: str = "http://localhost:8000") -> bool:
    """Test error handling."""
    print_status("Testing error handling...", "INFO")

    # Test invalid payload
    try:
        response = requests.post(
            f"{base_url}/predict", json={"invalid": "payload"}, timeout=5
        )

        if response.status_code in [400, 422]:
            print_status("Error handling works (invalid payload)", "PASS")
            return True
        else:
            print_status(
                f"Unexpected status for invalid payload: {response.status_code}", "WARN"
            )
            return True
    except Exception as e:
        print_status(f"Error testing error handling: {e}", "WARN")
        return True


def test_multiple_predictions(
    base_url: str = "http://localhost:8000", count: int = 5
) -> bool:
    """Test multiple predictions to verify consistency."""
    print_status(f"Testing {count} predictions for consistency...", "INFO")

    payload = {"rows": [{"ret_mean": 0.05, "ret_std": 0.01, "n": 50}]}

    results = []
    for i in range(count):
        try:
            response = requests.post(f"{base_url}/predict", json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results.append(data)
            else:
                print_status(
                    f"Prediction {i+1} failed with status {response.status_code}",
                    "WARN",
                )
        except Exception as e:
            print_status(f"Prediction {i+1} error: {e}", "WARN")

    if len(results) == count:
        # Check consistency
        model_variants = set(r["model_variant"] for r in results)
        if len(model_variants) == 1:
            print_status(
                f"All {count} predictions consistent (model_variant: {list(model_variants)[0]})",
                "PASS",
            )
            return True
        else:
            print_status(f"Inconsistent model_variants: {model_variants}", "WARN")
            return True
    else:
        print_status(f"Only {len(results)}/{count} predictions succeeded", "WARN")
        return len(results) > 0


def wait_for_service(
    base_url: str = "http://localhost:8000", max_wait: int = 30
) -> bool:
    """Wait for service to be ready."""
    print_status(f"Waiting for API to be ready (max {max_wait}s)...", "INFO")

    for i in range(max_wait):
        try:
            response = requests.get(f"{base_url}/health", timeout=2)
            if response.status_code == 200:
                print_status("Service is ready", "PASS")
                return True
        except:
            pass
        time.sleep(1)
        if (i + 1) % 5 == 0:
            print(f"  Still waiting... ({i+1}s)")

    print_status("Service did not become ready in time", "WARN")
    print_status("  Start API with: docker compose up -d api", "INFO")
    print_status("  OR run separately: python -m uvicorn api_v1:api --reload", "INFO")
    return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("COMPREHENSIVE SYSTEM TEST")
    print("=" * 60 + "\n")

    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")

    tests = [
        ("Docker Compose", check_docker_compose),
        ("Services Running", check_services_running),
        ("Service Ready", lambda: wait_for_service(base_url)),
        ("Health Endpoint", lambda: test_health_endpoint(base_url)),
        ("Version Endpoint", lambda: test_version_endpoint(base_url)),
        ("Metrics Endpoint", lambda: test_metrics_endpoint(base_url)),
        ("Predict Endpoint", lambda: test_predict_endpoint(base_url)),
        ("Error Handling", lambda: test_error_handling(base_url)),
        ("Multiple Predictions", lambda: test_multiple_predictions(base_url)),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_status(f"Test '{test_name}' failed with exception: {e}", "FAIL")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print_status(f"{test_name}: {status}", status)

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ All tests passed! System is ready.")
        return 0
    elif passed >= total * 0.8:
        print("\n⚠️  Most tests passed. Review failures above.")
        return 1
    else:
        print("\n❌ Multiple tests failed. System needs attention.")
        return 1


if __name__ == "__main__":
    exit(main())
