import os
import time
import requests
import statistics
from dotenv import load_dotenv

load_dotenv()

base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
endpoint = os.getenv("HEALTH_ENDPOINT", "/health")
n = int(os.getenv("LOAD_TEST_REQUESTS", "100"))

url = base_url.rstrip("/") + endpoint

def run_test():
    latencies = []

    for i in range(n):
        start = time.perf_counter()
        response = requests.get(url)
        latency = time.perf_counter() - start

        latencies.append(latency)

    # Latency report
    print(max(latencies))
    print(statistics.mean(latencies))
    print(min(latencies))

if __name__ == "__main__":
    run_test()
