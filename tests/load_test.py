import os
import time
import requests
import statistics
import concurrent.futures
from dotenv import load_dotenv

load_dotenv()

base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
n = int(os.getenv("LOAD_TEST_REQUESTS", "100"))

# Test the /predict endpoint with a sample payload
predict_url = base_url.rstrip("/") + "/predict"
payload = {
    "rows": [
        {"ret_mean": 0.001, "ret_std": 0.01, "n": 100}
    ]
}


def send_request():
    """Send a single prediction request and return latency and status code."""
    try:
        start = time.perf_counter()
        response = requests.post(predict_url, json=payload, timeout=10)
        latency = time.perf_counter() - start
        return latency, response.status_code, None
    except requests.exceptions.RequestException as e:
        latency = time.perf_counter() - start if 'start' in locals() else None
        return latency, None, str(e)


def run_test():
    """Run burst load test with concurrent requests."""
    print(f"Starting load test: {n} concurrent requests to {predict_url}")
    print("=" * 60)
    
    latencies = []
    status_codes = []
    errors = []
    
    # Send all requests concurrently
    start_time = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as executor:
        futures = [executor.submit(send_request) for _ in range(n)]
        for future in concurrent.futures.as_completed(futures):
            latency, status_code, error = future.result()
            if latency is not None:
                latencies.append(latency)
            if status_code is not None:
                status_codes.append(status_code)
            if error is not None:
                errors.append(error)
    
    total_time = time.perf_counter() - start_time
    
    # Calculate metrics
    if latencies:
        latencies_sorted = sorted(latencies)
        n_latencies = len(latencies)
        
        # Percentiles
        p50 = latencies_sorted[int(n_latencies * 0.50)]
        p95 = latencies_sorted[int(n_latencies * 0.95)]
        p99 = latencies_sorted[int(n_latencies * 0.99)]
        
        # Basic stats
        min_latency = min(latencies)
        max_latency = max(latencies)
        mean_latency = statistics.mean(latencies)
        median_latency = statistics.median(latencies)
        
        # Error rates
        success_count = sum(1 for sc in status_codes if sc == 200)
        error_count = len(errors) + len([sc for sc in status_codes if sc != 200])
        success_rate = (success_count / n) * 100 if n > 0 else 0
        
        # Throughput
        throughput = n / total_time if total_time > 0 else 0
        
        # Print report
        print("\n" + "=" * 60)
        print("LOAD TEST RESULTS")
        print("=" * 60)
        print(f"Total Requests: {n}")
        print(f"Successful (200): {success_count}")
        print(f"Errors: {error_count}")
        print(f"Success Rate: {success_rate:.2f}%")
        print(f"Total Time: {total_time:.3f}s")
        print(f"Throughput: {throughput:.2f} req/s")
        print("\nLatency Statistics (seconds):")
        print(f"  Min:    {min_latency:.4f}s")
        print(f"  Mean:   {mean_latency:.4f}s")
        print(f"  Median: {median_latency:.4f}s")
        print(f"  P50:    {p50:.4f}s")
        print(f"  P95:    {p95:.4f}s")
        print(f"  P99:    {p99:.4f}s")
        print(f"  Max:    {max_latency:.4f}s")
        
        if errors:
            print(f"\nErrors ({len(errors)}):")
            error_types = {}
            for error in errors:
                error_type = error.split(":")[0] if ":" in error else error
                error_types[error_type] = error_types.get(error_type, 0) + 1
            for error_type, count in error_types.items():
                print(f"  {error_type}: {count}")
        
        print("=" * 60)
        
        # Return summary for programmatic use
        return {
            "total_requests": n,
            "success_count": success_count,
            "error_count": error_count,
            "success_rate": success_rate,
            "throughput": throughput,
            "latency": {
                "min": min_latency,
                "mean": mean_latency,
                "median": median_latency,
                "p50": p50,
                "p95": p95,
                "p99": p99,
                "max": max_latency,
            }
        }
    else:
        print("ERROR: No successful requests!")
        return None


if __name__ == "__main__":
    run_test()
