import os
from pathlib import Path
import unittest

CONFIG_ENV = {
    "AIOPS_ENV": "test",
    "AIOPS_SERVICE_NAME": "aiops-test",
    "AIOPS_VERSION": "test-version",
    "AIOPS_HOST": "127.0.0.1",
    "AIOPS_PORT": "5000",
    "AIOPS_ALLOWED_ORIGINS": "http://test.invalid",
    "AIOPS_LOG_LEVEL": "INFO",
    "AIOPS_VERIFY_TLS": "true",
    "AIOPS_PROMETHEUS_TIMEOUT_SECONDS": "5",
    "AIOPS_MAX_QUERY_LENGTH": "2000",
    "AIOPS_RATE_LIMIT_PER_MINUTE": "120",
    "AIOPS_AUDIT_LOG_MAX_ENTRIES": "5000",
    "AIOPS_EVENT_STORE_MAX_ENTRIES": "1000",
    "AIOPS_SLO_TARGET": "99.5",
    "AIOPS_SLO_WINDOW_MINUTES": "60",
    "AIOPS_REFRESH_SECONDS": "30",
}


class OperationalFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous = {key: os.environ.get(key) for key in CONFIG_ENV}
        os.environ.update(CONFIG_ENV)
        import web_dashboard

        cls.module = web_dashboard
        cls.client = web_dashboard.app.test_client()

    @classmethod
    def tearDownClass(cls):
        for key, value in cls.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_liveness_is_available_without_dependencies(self):
        response = self.client.get("/health/live")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "alive")
        self.assertTrue(response.headers.get("X-Request-ID"))

    def test_readiness_fails_when_sources_are_not_configured(self):
        response = self.client.get("/health/ready")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["status"], "not_ready")
        self.assertIn("AIOPS_PROMETHEUS_URL", response.get_json()["missing"])

    def test_api_reports_integration_unavailable_instead_of_synthesizing_data(self):
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json()["error"]["code"], "integration_unavailable"
        )

    def test_query_requires_a_valid_bounded_json_body(self):
        missing = self.client.post("/api/query", json={})
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.get_json()["error"]["code"], "invalid_request")

        empty = self.client.post("/api/query", json={"query": "   "})
        self.assertEqual(empty.status_code, 400)

    def test_thresholds_require_external_persistence(self):
        response = self.client.post(
            "/api/set-thresholds", json={"cpu": 80, "mem": 85, "disk": 90}
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json()["error"]["code"], "integration_unavailable"
        )

    def test_template_does_not_render_source_data_as_html(self):
        template = Path(__file__).parents[1] / "templates" / "dashboard.html"
        content = template.read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", content)
        self.assertIn("textContent", content)
        self.assertNotIn("random.", content)


if __name__ == "__main__":
    unittest.main()
