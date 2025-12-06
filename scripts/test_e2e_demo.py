#!/usr/bin/env python3
"""
End-to-end test script to validate the repository is ready for demo.
This script:
1. Stops existing containers
2. Builds and starts all Docker services
3. Waits for services to be healthy
4. Verifies models exist
5. Tests all API endpoints
6. Provides a comprehensive report
"""

import sys
import subprocess
import time
import requests
import json
from pathlib import Path
from typing import Dict, List, Tuple

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{BOLD}{BLUE}{'=' * 70}{RESET}")
    print(f"{BOLD}{BLUE}{text.center(70)}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 70}{RESET}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{GREEN}✓{RESET} {text}")


def print_error(text: str):
    """Print error message."""
    print(f"{RED}✗{RESET} {text}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{YELLOW}⚠{RESET} {text}")


def print_info(text: str):
    """Print info message."""
    print(f"{BLUE}ℹ{RESET} {text}")


def run_command(
    cmd: List[str], check: bool = True, capture_output: bool = False
) -> Tuple[int, str]:
    """Run a shell command and return exit code and output."""
    try:
        result = subprocess.run(
            cmd, check=check, capture_output=capture_output, text=True
        )
        output = result.stdout if capture_output else ""
        return result.returncode, output
    except subprocess.CalledProcessError as e:
        if capture_output:
            return e.returncode, e.stdout + e.stderr
        return e.returncode, ""


def step_1_stop_containers() -> bool:
    """Step 1: Stop and remove existing containers."""
    print_header("STEP 1: Stopping Existing Containers")

    print_info("Stopping docker-compose services...")
    code, _ = run_command(["docker", "compose", "down"], check=False)

    if code == 0:
        print_success("Containers stopped successfully")
    else:
        print_warning("Some containers may not have been running")

    # Also try docker-compose down with -v to remove volumes if needed
    print_info("Cleaning up volumes (if any)...")
    run_command(["docker", "compose", "down", "-v"], check=False)

    return True


def step_2_build_containers() -> bool:
    """Step 2: Build Docker containers."""
    print_header("STEP 2: Building Docker Containers")

    print_info("Building API container...")
    code, output = run_command(
        ["docker", "compose", "build", "api"], capture_output=True
    )

    if code != 0:
        print_error(f"Failed to build API container: {output}")
        return False

    print_success("API container built successfully")
    return True


def step_3_start_services() -> bool:
    """Step 3: Start all Docker services."""
    print_header("STEP 3: Starting Docker Services")

    print_info("Starting all services (zookeeper, kafka, mlflow, api)...")
    code, output = run_command(["docker", "compose", "up", "-d"], capture_output=True)

    if code != 0:
        print_error(f"Failed to start services: {output}")
        return False

    print_success("Services started")
    print_info("Waiting for services to initialize...")

    return True


def step_4_wait_for_health() -> bool:
    """Step 4: Wait for all services to be healthy."""
    print_header("STEP 4: Waiting for Services to be Healthy")

    services = {
        "zookeeper": ("localhost", 2181),
        "kafka": ("localhost", 9092),
        "mlflow": ("localhost", 5001),
        "api": ("localhost", 8000),
    }

    max_wait = 120  # 2 minutes max
    start_time = time.time()

    for service_name, (host, port) in services.items():
        print_info(f"Waiting for {service_name}...")
        elapsed = 0

        while elapsed < max_wait:
            try:
                if service_name == "zookeeper":
                    # Check zookeeper via docker exec
                    code, _ = run_command(
                        [
                            "docker",
                            "exec",
                            "zookeeper",
                            "nc",
                            "-z",
                            "localhost",
                            "2181",
                        ],
                        check=False,
                    )
                    if code == 0:
                        print_success(f"{service_name} is healthy")
                        break
                elif service_name == "kafka":
                    # Check kafka via docker exec
                    code, _ = run_command(
                        [
                            "docker",
                            "exec",
                            "kafka",
                            "kafka-broker-api-versions",
                            "--bootstrap-server",
                            "localhost:9092",
                        ],
                        check=False,
                    )
                    if code == 0:
                        print_success(f"{service_name} is healthy")
                        break
                elif service_name == "mlflow":
                    # Check MLflow via HTTP
                    response = requests.get(f"http://{host}:{port}/", timeout=3)
                    if response.status_code == 200:
                        print_success(f"{service_name} is healthy")
                        break
                elif service_name == "api":
                    # Check API via health endpoint
                    response = requests.get(f"http://{host}:{port}/health", timeout=3)
                    if response.status_code == 200:
                        print_success(f"{service_name} is healthy")
                        break
            except Exception:
                pass

            time.sleep(2)
            elapsed = time.time() - start_time

        if elapsed >= max_wait:
            print_error(
                f"{service_name} did not become healthy within {max_wait} seconds"
            )
            return False

    print_success("All services are healthy!")
    return True


def step_5_verify_models() -> bool:
    """Step 5: Verify models exist and are loadable."""
    print_header("STEP 5: Verifying Models")

    artifacts_dir = project_root / "models" / "artifacts"
    required_models = ["xgb_model.pkl", "logistic_model.pkl"]

    all_exist = True
    for model_file in required_models:
        model_path = artifacts_dir / model_file
        if model_path.exists():
            size_kb = model_path.stat().st_size / 1024
            print_success(f"{model_file} exists ({size_kb:.1f} KB)")
        else:
            print_error(f"{model_file} NOT FOUND")
            all_exist = False

    # Try to verify models are loadable
    print_info("Verifying models are loadable...")
    code, _ = run_command(["python", "scripts/verify_models.py"], check=False)

    if code == 0:
        print_success("Models are loadable")
    else:
        print_warning("Some models may not be loadable (check output above)")

    return all_exist


def step_6_test_api_endpoints() -> Dict[str, bool]:
    """Step 6: Test all API endpoints."""
    print_header("STEP 6: Testing API Endpoints")

    results = {}
    base_url = "http://localhost:8000"

    # Test 1: Health endpoint
    print_info("Testing /health endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_success(f"/health: {data}")
            results["health"] = True
        else:
            print_error(f"/health returned status {response.status_code}")
            results["health"] = False
    except Exception as e:
        print_error(f"/health failed: {e}")
        results["health"] = False

    # Test 2: Version endpoint
    print_info("Testing /version endpoint...")
    try:
        response = requests.get(f"{base_url}/version", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_success(
                f"/version: model={data.get('model')}, version={data.get('version')}"
            )
            results["version"] = True
        else:
            print_error(f"/version returned status {response.status_code}")
            results["version"] = False
    except Exception as e:
        print_error(f"/version failed: {e}")
        results["version"] = False

    # Test 3: Prediction endpoint
    print_info("Testing /predict endpoint...")
    test_data = {
        "rows": [
            {"ret_mean": 0.001, "ret_std": 0.01, "n": 60},
            {"ret_mean": 0.005, "ret_std": 0.05, "n": 60},
            {"ret_mean": -0.002, "ret_std": 0.02, "n": 60},
        ]
    }
    try:
        response = requests.post(f"{base_url}/predict", json=test_data, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print_success(
                f"/predict: {len(data.get('scores', []))} predictions returned"
            )
            print_info(f"  Model variant: {data.get('model_variant')}")
            print_info(f"  Sample scores: {data.get('scores', [])[:3]}")
            results["predict"] = True
        else:
            print_error(f"/predict returned status {response.status_code}")
            print_error(f"  Response: {response.text[:200]}")
            results["predict"] = False
    except Exception as e:
        print_error(f"/predict failed: {e}")
        results["predict"] = False

    # Test 4: Metrics endpoint (if available)
    print_info("Testing /metrics endpoint...")
    try:
        response = requests.get(f"{base_url}/metrics", timeout=5)
        if response.status_code == 200:
            print_success("/metrics endpoint accessible")
            results["metrics"] = True
        else:
            print_warning(
                f"/metrics returned status {response.status_code} (may not be implemented)"
            )
            results["metrics"] = False
    except Exception as e:
        print_warning(f"/metrics failed: {e} (may not be implemented)")
        results["metrics"] = False

    return results


def step_7_test_mlflow() -> bool:
    """Step 7: Test MLflow connectivity."""
    print_header("STEP 7: Testing MLflow Connectivity")

    try:
        response = requests.get("http://localhost:5001/", timeout=5)
        if response.status_code == 200:
            print_success("MLflow UI is accessible at http://localhost:5001")
            return True
        else:
            print_warning(f"MLflow returned status {response.status_code}")
            return False
    except Exception as e:
        print_warning(f"MLflow connectivity check failed: {e}")
        print_info("(This is OK if using local models)")
        return False


def step_8_run_demo_test() -> bool:
    """Step 8: Run the test_demo.py script."""
    print_header("STEP 8: Running Demo Test Script")

    print_info("Running scripts/test_demo.py...")
    code, output = run_command(
        ["python", "scripts/test_demo.py"], check=False, capture_output=True
    )

    # Print the output
    print(output)

    if code == 0:
        print_success("Demo test script passed!")
        return True
    else:
        print_error("Demo test script failed")
        return False


def print_summary(results: Dict[str, bool]):
    """Print final summary."""
    print_header("END-TO-END TEST SUMMARY")

    all_passed = True
    for test_name, passed in results.items():
        if passed:
            print_success(f"{test_name}")
        else:
            print_error(f"{test_name}")
            all_passed = False

    print()
    print("=" * 70)
    if all_passed:
        print(f"{BOLD}{GREEN}✓ ALL TESTS PASSED - Repository is ready for demo!{RESET}")
    else:
        print(f"{BOLD}{RED}✗ SOME TESTS FAILED - Review issues above{RESET}")
    print("=" * 70)

    # Print service status
    print(f"\n{BOLD}Service Status:{RESET}")
    code, output = run_command(["docker", "compose", "ps"], capture_output=True)
    print(output)

    # Print useful commands
    print(f"\n{BOLD}Useful Commands:{RESET}")
    print("  View API logs:    docker logs ml-prediction-api")
    print("  View MLflow:      http://localhost:5001")
    print("  View API docs:    http://localhost:8000/docs")
    print("  Test API:         python scripts/test_demo.py")
    print("  Stop services:    docker compose down")


def main():
    """Run the complete end-to-end test."""
    print_header("END-TO-END DEMO VALIDATION TEST")

    results = {}

    # Step 1: Stop existing containers
    results["Stop Containers"] = step_1_stop_containers()
    if not results["Stop Containers"]:
        print_error("Failed to stop containers")
        return 1

    # Step 2: Build containers
    results["Build Containers"] = step_2_build_containers()
    if not results["Build Containers"]:
        print_error("Failed to build containers")
        return 1

    # Step 3: Start services
    results["Start Services"] = step_3_start_services()
    if not results["Start Services"]:
        print_error("Failed to start services")
        return 1

    # Give services a moment to start
    print_info("Waiting 10 seconds for services to initialize...")
    time.sleep(10)

    # Step 4: Wait for health
    results["Services Healthy"] = step_4_wait_for_health()
    if not results["Services Healthy"]:
        print_error("Services did not become healthy")
        print_warning("Continuing with tests anyway...")

    # Step 5: Verify models
    results["Models Verified"] = step_5_verify_models()
    if not results["Models Verified"]:
        print_error("Model verification failed")
        return 1

    # Step 6: Test API endpoints
    api_results = step_6_test_api_endpoints()
    results["API Health"] = api_results.get("health", False)
    results["API Version"] = api_results.get("version", False)
    results["API Predict"] = api_results.get("predict", False)
    results["API Metrics"] = api_results.get("metrics", False)

    # Step 7: Test MLflow
    results["MLflow Accessible"] = step_7_test_mlflow()

    # Step 8: Run demo test script
    results["Demo Test Script"] = step_8_run_demo_test()

    # Print summary
    print_summary(results)

    # Return exit code
    all_passed = all(results.values())
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
