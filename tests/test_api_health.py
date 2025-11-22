import os
import sys

# Make sure Python can find the project root (where api_v1.py lives)
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient
from api_v1 import api  # <- IMPORTANT: your FastAPI instance is named `api`, not `app`

client = TestClient(api)


def test_health_endpoint():
    """Basic integration test: /health should return status: ok."""
    response = client.get("/health")

    # 1) Endpoint should work
    assert response.status_code == 200

    # 2) Response body should contain { "status": "ok" }
    data = response.json()
    assert data.get("status") == "ok"
