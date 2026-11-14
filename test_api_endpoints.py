"""Optional read-only integration smoke test.

Set AIOPS_TEST_BASE_URL and AIOPS_TEST_TIMEOUT_SECONDS explicitly before running.
This test never invokes mutation routes.
"""

import os

import pytest
import requests

ENDPOINTS = (
    "/api/status",
    "/api/incidents",
    "/api/alerts",
    "/api/self-healing",
    "/api/health-heatmap",
    "/api/historical-trends",
    "/api/anomaly-timeline",
    "/api/log-events",
    "/api/ai-recommendations",
    "/api/rca-insights",
    "/api/grouped-incidents",
    "/api/ml-insights",
    "/api/performance-metrics",
    "/api/self-healing-timeline",
)


def test_read_only_api_endpoints():
    base_url = os.getenv("AIOPS_TEST_BASE_URL")
    timeout_value = os.getenv("AIOPS_TEST_TIMEOUT_SECONDS")
    if not base_url or not timeout_value:
        pytest.skip(
            "Set AIOPS_TEST_BASE_URL and AIOPS_TEST_TIMEOUT_SECONDS "
            "to run integration smoke checks"
        )

    headers = {}
    api_key = os.getenv("AIOPS_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    timeout = float(timeout_value)
    for endpoint in ENDPOINTS:
        response = requests.get(
            f"{base_url.rstrip('/')}{endpoint}",
            headers=headers,
            timeout=timeout,
        )
        assert response.status_code < 500 or response.status_code == 503, (
            f"{endpoint} returned unexpected HTTP {response.status_code}"
        )
