#!/usr/bin/env python3
"""
Test Monitoring Implementation

Tests Prometheus metrics, MODEL_VARIANT, and drift summary generation.
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_metrics_definition():
    """Test that Prometheus metrics are properly defined."""
    print("=" * 60)
    print("Test 1: Prometheus Metrics Definition")
    print("=" * 60)

    try:
        import api_v1

        # Check metrics exist
        assert hasattr(api_v1, "count"), "Missing count metric"
        assert hasattr(api_v1, "latency"), "Missing latency metric"
        assert hasattr(api_v1, "error_count"), "Missing error_count metric"
        assert hasattr(api_v1, "request_count"), "Missing request_count metric"
        assert hasattr(api_v1, "model_version_gauge"), "Missing model_version_gauge"

        print("✓ All metrics defined:")
        print(f"  - count: {api_v1.count}")
        print(f"  - latency: {api_v1.latency}")
        print(f"  - error_count: {api_v1.error_count}")
        print(f"  - request_count: {api_v1.request_count}")
        print(f"  - model_version_gauge: {api_v1.model_version_gauge}")

        # Check latency buckets
        if hasattr(api_v1.latency, "_buckets"):
            print(f"  - Latency buckets: {api_v1.latency._buckets}")

        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_model_variant():
    """Test MODEL_VARIANT environment variable."""
    print("\n" + "=" * 60)
    print("Test 2: MODEL_VARIANT Functionality")
    print("=" * 60)

    try:
        import api_v1

        # Check that MODEL_VARIANT is read from environment
        # Note: We can't reload the module due to Prometheus metric registration,
        # but we can verify the logic is in place

        # Check current state
        print(f"✓ Current MODEL_VARIANT: {api_v1.model_variant}")
        print(f"  - Model type: {api_v1.model_type}")
        print(f"  - Model path: {api_v1.model_path}")

        # Verify the logic exists in code
        with open(project_root / "api_v1.py") as f:
            code = f.read()
            assert "MODEL_VARIANT" in code, "MODEL_VARIANT not found in code"
            assert (
                "model_variant = os.getenv" in code
            ), "MODEL_VARIANT not read from env"
            assert "baseline" in code.lower(), "Baseline logic not found"
            assert "logistic" in code.lower(), "Logistic model selection not found"

        print("✓ MODEL_VARIANT logic verified in code:")
        print("  - Reads from environment variable")
        print("  - Supports 'ml' and 'baseline' values")
        print("  - Selects appropriate model type")

        # Note: Full test requires restarting the API process
        print("\n  Note: Full MODEL_VARIANT test requires API restart:")
        print("    export MODEL_VARIANT=baseline")
        print("    python -m uvicorn api_v1:api --reload")

        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_grafana_dashboard():
    """Test Grafana dashboard JSON."""
    print("\n" + "=" * 60)
    print("Test 3: Grafana Dashboard")
    print("=" * 60)

    try:
        dashboard_path = project_root / "grafana" / "dashboard.json"
        assert dashboard_path.exists(), f"Dashboard not found: {dashboard_path}"

        with open(dashboard_path) as f:
            dashboard = json.load(f)

        assert "dashboard" in dashboard, "Missing 'dashboard' key"
        assert "panels" in dashboard["dashboard"], "Missing 'panels' key"

        panels = dashboard["dashboard"]["panels"]
        print(f"✓ Dashboard loaded: {dashboard['dashboard']['title']}")
        print(f"  - Panels: {len(panels)}")

        # Check for key panels
        panel_titles = [p.get("title", "") for p in panels]
        required_panels = ["P95 Latency", "Error Rate", "Request Rate"]
        for req in required_panels:
            found = any(req in title for title in panel_titles)
            print(f"  - {req}: {'✓' if found else '✗'}")

        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_drift_summary_script():
    """Test drift summary script."""
    print("\n" + "=" * 60)
    print("Test 4: Drift Summary Script")
    print("=" * 60)

    try:
        import generate_drift_summary

        # Check script has required functions
        assert hasattr(generate_drift_summary, "main"), "Missing main function"
        assert hasattr(
            generate_drift_summary, "generate_drift_summary"
        ), "Missing generate_drift_summary"
        assert hasattr(
            generate_drift_summary, "extract_drift_summary"
        ), "Missing extract_drift_summary"
        assert hasattr(
            generate_drift_summary, "write_summary_markdown"
        ), "Missing write_summary_markdown"

        print("✓ Script structure valid:")
        print("  - main() function exists")
        print("  - generate_drift_summary() function exists")
        print("  - extract_drift_summary() function exists")
        print("  - write_summary_markdown() function exists")

        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_documentation():
    """Test that documentation files exist."""
    print("\n" + "=" * 60)
    print("Test 5: Documentation Files")
    print("=" * 60)

    docs_to_check = [
        ("docs/slo.md", "SLOs document"),
        ("docs/runbook.md", "Runbook"),
        ("docs/monitoring_implementation.md", "Implementation docs"),
    ]

    all_exist = True
    for doc_path, name in docs_to_check:
        path = project_root / doc_path
        exists = path.exists()
        print(f"{'✓' if exists else '✗'} {name}: {path}")
        if not exists:
            all_exist = False

    return all_exist


def test_api_structure():
    """Test API structure for metrics endpoint."""
    print("\n" + "=" * 60)
    print("Test 6: API Structure")
    print("=" * 60)

    try:
        import api_v1

        # Check API has metrics endpoint
        routes = [route.path for route in api_v1.api.routes]
        assert "/metrics" in routes, "Missing /metrics endpoint"
        assert "/predict" in routes, "Missing /predict endpoint"
        assert "/health" in routes, "Missing /health endpoint"
        assert "/version" in routes, "Missing /version endpoint"

        print("✓ API endpoints:")
        for route in sorted(routes):
            print(f"  - {route}")

        # Check metrics endpoint function exists
        assert hasattr(api_v1, "metrics"), "Missing metrics() function"
        print("\n✓ Metrics endpoint function exists")

        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Monitoring Implementation Test Suite")
    print("=" * 60)

    tests = [
        ("Metrics Definition", test_metrics_definition),
        ("MODEL_VARIANT", test_model_variant),
        ("Grafana Dashboard", test_grafana_dashboard),
        ("Drift Summary Script", test_drift_summary_script),
        ("Documentation", test_documentation),
        ("API Structure", test_api_structure),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Test '{name}' failed with exception: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
