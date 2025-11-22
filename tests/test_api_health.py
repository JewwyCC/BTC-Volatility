from fastapi.testclient import TestClient
from api_v1 import api  # IMPORTANT: your FastAPI instance is named `api`, not `app`


client = TestClient(api)


def test_health():
    """Basic integration test: /health should return status: ok."""
    response = client.get("/health")

    # 1) Endpoint should work
    assert response.status_code == 200

    # 2) Response body should contain {"status": "ok"}
    data = response.json()
    assert data.get("status") == "ok"
