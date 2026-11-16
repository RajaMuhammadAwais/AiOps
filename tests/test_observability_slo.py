import re
from unittest.mock import patch

from src.platform.observability import MetricsRegistry


def _metric_value(text: str, prefix: str) -> float:
    for line in text.splitlines():
        if line.startswith(prefix + "{"):
            return float(line.rsplit(" ", 1)[1])
    raise AssertionError(f"metric not found: {prefix}")


def _bucket_counts(text: str) -> dict[str, int]:
    result = {}
    for line in text.splitlines():
        if line.startswith("aiops_http_request_duration_seconds_bucket{"):
            match = re.search(r'le="([^"]+)"', line)
            assert match is not None
            result[match.group(1)] = int(line.rsplit(" ", 1)[1])
    return result


def test_request_availability_policy_and_error_budget_math_are_explicit():
    registry = MetricsRegistry()
    statuses = [200] * 97 + [302, 429, 503, 401, 404]
    for status in statuses:
        registry.observe("GET", "/api/status", status, 0.025)

    snapshot = registry.slo_snapshot(target=99.5, window_minutes=60)

    assert snapshot["source"] == "process_local"
    assert snapshot["aggregation_scope"].startswith("single process")
    assert snapshot["good_events"] == 98
    assert snapshot["total_events"] == 100
    assert snapshot["bad_events"] == 2
    assert snapshot["excluded_client_errors"] == 2
    assert snapshot["availability_percent"] == 98.0
    assert snapshot["within_objective"] is False
    assert snapshot["error_budget_consumed_percent"] == 400.0
    assert snapshot["error_budget_remaining_percent"] == 0.0
    assert snapshot["burn_rate"] == 4.0
    assert snapshot["status_policy"]["429"].startswith("bad event")
    assert snapshot["status_policy"]["4xx_except_429"].startswith("excluded")


def test_empty_window_is_no_data_not_a_false_100_percent_availability():
    registry = MetricsRegistry()
    registry.observe("POST", "/api/query", 400, 0.02)

    snapshot = registry.slo_snapshot(target=99.5, window_minutes=60)

    assert snapshot["measurement_state"] == "no_data"
    assert snapshot["good_events"] == 0
    assert snapshot["total_events"] == 0
    assert snapshot["excluded_client_errors"] == 1
    assert snapshot["availability_percent"] is None
    assert snapshot["within_objective"] is None
    assert snapshot["error_budget_consumed_percent"] is None


def test_local_slo_window_discards_expired_samples():
    registry = MetricsRegistry()
    with patch("src.platform.observability.time.time", return_value=0):
        registry.observe("GET", "/api/status", 200, 0.01)
    with patch("src.platform.observability.time.time", return_value=100):
        registry.observe("GET", "/api/status", 503, 0.02)
        snapshot = registry.slo_snapshot(target=99.0, window_minutes=1)

    assert snapshot["good_events"] == 0
    assert snapshot["bad_events"] == 1
    assert snapshot["total_events"] == 1


def test_shared_slo_snapshot_labels_aggregated_source_and_handles_no_data():
    measured = MetricsRegistry.shared_slo_snapshot(198.0, 200.0, 99.5, 60)
    empty = MetricsRegistry.shared_slo_snapshot(0.0, 0.0, 99.5, 60)

    assert measured["source"] == "prometheus"
    assert measured["aggregation_scope"].startswith("all instances")
    assert measured["availability_percent"] == 99.0
    assert measured["error_budget_consumed_percent"] == 200.0
    assert empty["measurement_state"] == "no_data"
    assert empty["availability_percent"] is None


def test_histogram_buckets_are_cumulative_with_fixed_boundaries_and_lifetime_sum():
    registry = MetricsRegistry()
    registry.observe("GET", "/api/status", 200, 0.003)
    registry.observe("GET", "/api/status", 500, 0.02)
    registry.observe("GET", "/api/status", 503, 0.3)

    exposition = registry.prometheus("aiops-test")
    buckets = _bucket_counts(exposition)

    assert "# TYPE aiops_http_request_duration_seconds histogram" in exposition
    assert buckets["0.005"] == 1
    assert buckets["0.025"] == 2
    assert buckets["0.25"] == 2
    assert buckets["0.5"] == 3
    assert buckets["+Inf"] == 3
    assert _metric_value(exposition, "aiops_http_request_duration_seconds_sum") == 0.323
    assert _metric_value(exposition, "aiops_http_request_duration_seconds_count") == 3


def test_histograms_from_multiple_workers_are_additive_with_identical_series_shape():
    worker_a = MetricsRegistry()
    worker_b = MetricsRegistry()
    worker_a.observe("GET", "/api/status", 200, 0.02)
    worker_b.observe("GET", "/api/status", 503, 0.3)

    a = _bucket_counts(worker_a.prometheus("aiops-test"))
    b = _bucket_counts(worker_b.prometheus("aiops-test"))
    combined = {bound: a[bound] + b[bound] for bound in a}

    assert combined["0.005"] == 0
    assert combined["0.025"] == 1
    assert combined["0.25"] == 1
    assert combined["0.5"] == 2
    assert combined["+Inf"] == 2


def test_method_and_route_labels_are_stable_and_bounded():
    registry = MetricsRegistry()
    registry.observe("TRACE", "/api/items/<item_id>", 200, 0.01)
    exposition = registry.prometheus('service"name')

    assert 'service="service\\"name"' in exposition
    assert 'method="OTHER"' in exposition
    assert 'route="/api/items/<item_id>"' in exposition
    assert "TRACE" not in exposition
