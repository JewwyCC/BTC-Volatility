import sys
from pathlib import Path

from fastapi.testclient import TestClient

# --- make project root importable for CI / pytest ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api_v1 import api  # noqa: E402  <- tell Ruff to ignore “import not at top”

# ----------------------------------------------------

client = TestClient(api)


def test_health_ok():
    """Basic integration test: /health should return status: ok."""
    response = client.get("/health")

    # 1) Endpoint should work
    assert response.status_code == 200

    # 2) Response body should contain {"status": "ok"}
    data = response.json()
    assert data.get("status") == "ok"
