# tests/test_api_health.py
import os
import sys

from fastapi.testclient import TestClient
from api_v1 import api  # IMPORTANT: FastAPI instance is named `api`, not `app`

# After imports: adjust sys.path so pytest can find api_v1.py
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

client = TestClient(api)


def test_health():
    """Basic integration test: /health should return status: ok."""
    response = client.get("/health")

    # 1) Endpoint should work
    assert response.status_code == 200

    # 2) Response body should contain {"status": "ok"}
    data = response.json()
    assert data.get("status") == "ok"
